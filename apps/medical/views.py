from datetime import timedelta
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from apps.core.decorators.error_handler import api_error_handler
from apps.core.decorators.rate_limit import rate_limit
from apps.core.responses.api_response import APIResponse
from apps.core.exceptions.base_exceptions import PrivacyError, ValidationError
from apps.core.permissions import IsAdminOrStaff, IsPatient
from .models import MedicalRecord
from .serializers import (
    MedicalRecordSerializer,
    MedicalRecordCreateSerializer,
    MedicalRecordUpdateSerializer,
    MedicalRecordFilterSerializer,
    MedicalRecordExportSerializer,
    MedicalRecordAuditSerializer,
)
from .services import MedicalRecordService


class MedicalRecordViewSet(ModelViewSet):
    """
    Unified ViewSet for medical record operations.

    Provides comprehensive medical record management with:
    - CRUD operations with role-based access control
    - Advanced filtering and searching
    - Statistics and analytics
    - Record exports
    - Confidentiality management
    - Follow-up tracking

    **Authentication:** Required
    **Permissions:** Based on user role (patient, specialist, admin/staff)
    """

    queryset = MedicalRecord.objects.select_related(
        "patient", "specialist", "specialist__user", "appointment"
    )

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = {
        "confidentiality_level": ["exact"],
        "patient__id": ["exact"],
        "specialist__id": ["exact"],
        "appointment__id": ["exact"],
    }
    search_fields = [
        "diagnosis",
        "prescription",
        "notes",
        "recommendations",
    ]
    ordering_fields = [
        "created_at",
        "updated_at",
        "follow_up_date",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Get queryset with service-driven access control"""
        return MedicalRecordService.get_filtered_records(
            user=self.request.user, filters=self.request.query_params
        )

    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ["change_confidentiality", "audit_log"]:
            return [IsAdminOrStaff()]
        elif self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated()]
        else:
            return [IsAuthenticated()]

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return MedicalRecordCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return MedicalRecordUpdateSerializer
        return MedicalRecordSerializer

    @api_error_handler
    @rate_limit(profile="READ_OPERATION", scope="medical_record_list")
    def list(self, request, *args, **kwargs):
        """List medical records with advanced filtering and pagination"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return APIResponse.from_paginated_response(
                self.paginator,
                serializer.data,
                message="Medical records retrieved successfully",
            )

        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(
            message="Medical records retrieved successfully",
            data=serializer.data,
        )

    @api_error_handler
    @rate_limit(profile="READ_OPERATION", scope="medical_record_detail")
    def retrieve(self, request, *args, **kwargs):
        """Get medical record details with permission flags"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # Add permission flags
        data = serializer.data
        data["can_edit"] = MedicalRecordService.can_edit_record(request.user, instance)
        data["can_delete"] = MedicalRecordService.can_delete_record(
            request.user, instance
        )

        return APIResponse.success(
            message="Medical record details retrieved",
            data=data,
        )

    @api_error_handler
    @rate_limit(profile="WRITE_OPERATION", scope="medical_record_create")
    def create(self, request, *args, **kwargs):
        """Create a new medical record"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        medical_record = MedicalRecordService.create_medical_record(
            user=request.user, **serializer.validated_data
        )

        return APIResponse.created(
            message="Medical record created successfully",
            data=MedicalRecordSerializer(medical_record).data,
        )

    @api_error_handler
    @rate_limit(profile="WRITE_OPERATION", scope="medical_record_update")
    def update(self, request, *args, **kwargs):
        """Update a medical record"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        medical_record = MedicalRecordService.update_medical_record(
            user=request.user, medical_record=instance, **serializer.validated_data
        )

        return APIResponse.success(
            message="Medical record updated successfully",
            data=MedicalRecordSerializer(medical_record).data,
        )

    @api_error_handler
    @rate_limit(profile="WRITE_OPERATION", scope="medical_record_delete")
    def destroy(self, request, *args, **kwargs):
        """Delete a medical record"""
        instance = self.get_object()
        MedicalRecordService.delete_medical_record(
            user=request.user, medical_record=instance
        )

        return APIResponse.success(message="Medical record deleted successfully")

    @api_error_handler
    @rate_limit(profile="READ_OPERATION", scope="patient_records")
    @action(detail=False, methods=["get"], url_path="patient-records")
    def patient_records(self, request):
        """Get all medical records for current patient"""
        if not request.user.is_authenticated or not request.user.is_patient():
            raise PrivacyError("Only patients can access their medical records")

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return APIResponse.from_paginated_response(
                self.paginator,
                serializer.data,
                message="Patient medical records retrieved",
            )

        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(
            message="Patient medical records retrieved",
            data=serializer.data,
        )

    @api_error_handler
    @rate_limit(profile="READ_OPERATION", scope="upcoming_follow_ups")
    @action(detail=False, methods=["get"], url_path="upcoming-follow-ups")
    def upcoming_follow_ups(self, request):
        """Get upcoming follow-ups for the next 30 days"""
        today = timezone.now().date()
        thirty_days_later = today + timedelta(days=30)

        queryset = (
            self.filter_queryset(self.get_queryset())
            .filter(
                follow_up_date__isnull=False,
                follow_up_date__gte=today,
                follow_up_date__lte=thirty_days_later,
            )
            .order_by("follow_up_date")
        )

        page = self.paginate_queryset(queryset)
        summary = {
            "total_upcoming": queryset.count(),
            "date_range": {
                "start": today.isoformat(),
                "end": thirty_days_later.isoformat(),
            },
        }
        if page:
            serializer = self.get_serializer(page, many=True)
            return APIResponse.from_paginated_response(
                self.paginator,
                serializer.data,
                message="Upcoming follow-ups retrieved",
                metadata={"summary": summary},
            )

        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(
            message="Upcoming follow-ups retrieved",
            data=serializer.data,
            metadata={"summary": summary},
        )

    @api_error_handler
    @rate_limit(profile="READ_OPERATION", scope="medical_stats")
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """Get medical record statistics and analytics"""
        period = request.query_params.get("period", "month")
        statistics = MedicalRecordService.get_statistics(
            user=request.user, period=period
        )

        return APIResponse.success(
            message="Medical record statistics retrieved",
            data=statistics,
        )

    @api_error_handler
    @rate_limit(profile="WRITE_OPERATION", scope="medical_confidentiality")
    @action(detail=True, methods=["post"], url_path="change-confidentiality")
    def change_confidentiality(self, request, pk=None):
        """Change confidentiality level of a medical record (admin/staff only)"""
        instance = self.get_object()
        new_level = request.data.get("confidentiality_level")

        if not new_level or new_level not in dict(
            MedicalRecord.CONFIDENTIALITY_CHOICES
        ):
            raise ValidationError(detail="Invalid confidentiality level")

        new_level = MedicalRecordService.validate_confidentiality_level(
            new_level, instance.diagnosis
        )

        instance.confidentiality_level = new_level
        instance.save()

        return APIResponse.success(
            message="Confidentiality level updated",
            data=MedicalRecordSerializer(instance).data,
        )

    @api_error_handler
    @rate_limit(profile="WRITE_OPERATION", scope="medical_export")
    @action(detail=False, methods=["post"], url_path="export")
    def export_records(self, request):
        """Export medical records in specified format"""
        export_serializer = MedicalRecordExportSerializer(data=request.data)
        export_serializer.is_valid(raise_exception=True)

        filters = export_serializer.validated_data
        records = MedicalRecordService.get_filtered_records(
            user=request.user,
            filters={
                "start_date": filters["start_date"],
                "end_date": filters["end_date"],
                "patient_id": filters.get("patient_id"),
            },
        )

        export_format = filters["format"]

        return APIResponse.success(
            message=f"Export generated in {export_format.upper()} format",
            data={
                "format": export_format,
                "record_count": records.count(),
                "download_url": None,  # Placeholder for actual download URL
                "expires_at": (timezone.now() + timedelta(hours=24)).isoformat(),
            },
        )

    @api_error_handler
    @rate_limit(profile="READ_OPERATION", scope="medical_audit")
    @action(detail=False, methods=["get"], url_path="audit-log")
    def audit_log(self, request):
        """Get audit log for medical records (admin/staff only)"""
        if not request.user.is_staff:
            raise PrivacyError("Only admins/staff can access audit logs")

        audit_serializer = MedicalRecordAuditSerializer(data=request.query_params)
        audit_serializer.is_valid(raise_exception=True)

        # Placeholder for actual audit log implementation
        audit_data = {
            "query": audit_serializer.validated_data,
            "logs": [],
            "total_entries": 0,
        }

        return APIResponse.success(
            message="Audit log retrieved",
            data=audit_data,
        )
