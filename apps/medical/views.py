from datetime import timedelta
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.decorators.error_handler import api_error_handler
from core.responses.api_response import APIResponse
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


class MedicalRecordViewSet(viewsets.ModelViewSet):
    """
    Unified ViewSet to handle all medical record operations
    """

    permission_classes = [IsAuthenticated]
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
        """Get queryset with access control"""
        user = self.request.user
        queryset = MedicalRecord.objects.select_related(
            "patient", "specialist", "specialist__user", "appointment"
        )

        # Apply access control based on user type
        if user.user_type == "patient":
            queryset = queryset.filter(patient=user)
            # Patients can't see highly sensitive records
            queryset = queryset.exclude(confidentiality_level="highly_sensitive")

        elif user.user_type == "specialist":
            if hasattr(user, "specialist_profile"):
                queryset = queryset.filter(specialist=user.specialist_profile)

        elif user.user_type == "staff":
            queryset = queryset.filter(confidentiality_level="standard")

        # Admin can see everything (no filter)

        return queryset

    def get_serializer_class(self):
        """Return the appropriate serializer based on the action"""
        if self.action == "create":
            return MedicalRecordCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return MedicalRecordUpdateSerializer
        return MedicalRecordSerializer

    @api_error_handler
    def list(self, request, *args, **kwargs):
        """List medical records with advanced filtering"""
        filter_serializer = MedicalRecordFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)

        # Get filtered records with business logic
        records = MedicalRecordService.get_filtered_records(
            user=request.user, filters=filter_serializer.validated_data
        )

        queryset = self.filter_queryset(records)
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(
            message="Medical records retrieved successfully", data=serializer.data
        )

    @api_error_handler
    def retrieve(self, request, *args, **kwargs):
        """Get medical record details"""
        instance = self.get_object()

        # Check access with business logic
        if not MedicalRecordService.can_access_record(request.user, instance):
            raise PermissionDenied("You do not have permission to view this record")

        serializer = self.get_serializer(instance)

        # Add permission flags
        data = serializer.data
        data["can_edit"] = MedicalRecordService.can_edit_record(request.user, instance)
        data["can_delete"] = MedicalRecordService.can_delete_record(
            request.user, instance
        )

        return APIResponse.success(
            message="Medical record details retrieved", data=data
        )

    @api_error_handler
    def create(self, request, *args, **kwargs):
        """Create new medical record"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Use service for business logic
        medical_record = MedicalRecordService.create_medical_record(
            user=request.user, **serializer.validated_data
        )

        return APIResponse.created(
            message="Medical record created successfully",
            data=MedicalRecordSerializer(medical_record).data,
        )

    @api_error_handler
    def update(self, request, *args, **kwargs):
        """Update medical record"""
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
    def destroy(self, request, *args, **kwargs):
        """Delete medical record"""
        instance = self.get_object()

        MedicalRecordService.delete_medical_record(
            user=request.user, medical_record=instance
        )

        return APIResponse.success(message="Medical record deleted successfully")

    @api_error_handler
    @action(detail=False, methods=["get"], url_path="patient-records")
    def patient_records(self, request):
        """Get medical records for current patient"""
        if request.user.user_type != "patient":
            raise PermissionDenied("Only patients can access their own records")

        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(
            message="Patient medical records retrieved", data=serializer.data
        )

    @api_error_handler
    @action(detail=False, methods=["get"], url_path="upcoming-follow-ups")
    def upcoming_follow_ups(self, request):
        """Get upcoming follow-ups"""

        # Determine date range (next 30 days)
        today = timezone.now().date()
        thirty_days_later = today + timedelta(days=30)

        # Get records with follow-ups
        queryset = (
            self.get_queryset()
            .filter(
                follow_up_date__isnull=False,
                follow_up_date__gte=today,
                follow_up_date__lte=thirty_days_later,
            )
            .order_by("follow_up_date")
        )

        # Group by patient
        from django.db.models import Q

        if request.user.user_type == "specialist":
            queryset = queryset.filter(specialist=request.user.specialist_profile)

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)

        # Add summary
        summary = {
            "total_upcoming": queryset.count(),
            "date_range": {
                "start": today.isoformat(),
                "end": thirty_days_later.isoformat(),
            },
        }

        return APIResponse.success(
            message="Upcoming follow-ups retrieved",
            data={"summary": summary, "records": serializer.data},
        )

    @api_error_handler
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """Get medical record statistics"""
        # Validate parameters
        period = request.query_params.get("period", "month")

        # Use service for business logic
        statistics = MedicalRecordService.get_statistics(
            user=request.user, period=period
        )

        return APIResponse.success(
            message="Medical record statistics retrieved", data=statistics
        )

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="change-confidentiality")
    def change_confidentiality(self, request, pk=None):
        """Change confidentiality level (admin only)"""
        instance = self.get_object()

        # Check permissions
        if request.user.user_type != "admin":
            raise PermissionDenied("Only admins can change confidentiality level")

        new_level = request.data.get("confidentiality_level")
        if not new_level or new_level not in dict(
            MedicalRecord.CONFIDENTIALITY_CHOICES
        ):
            raise ValidationError(detail="Invalid confidentiality level")

        # Validate with business logic
        new_level = MedicalRecordService.validate_confidentiality_level(
            new_level, instance.diagnosis
        )

        # Update
        instance.confidentiality_level = new_level
        instance.save()

        # Log change (placeholder)
        # MedicalRecordAuditService.log_confidentiality_change(instance, request.user, new_level)

        return APIResponse.success(
            message="Confidentiality level updated",
            data=MedicalRecordSerializer(instance).data,
        )

    @api_error_handler
    @action(detail=False, methods=["post"], url_path="export")
    def export_records(self, request):
        """Export medical records"""
        # Validate export parameters
        export_serializer = MedicalRecordExportSerializer(data=request.data)
        export_serializer.is_valid(raise_exception=True)

        # Get records with access control
        filters = export_serializer.validated_data
        records = MedicalRecordService.get_filtered_records(
            user=request.user,
            filters={
                "start_date": filters["start_date"],
                "end_date": filters["end_date"],
                "patient_id": filters.get("patient_id"),
            },
        )

        # Export logic (placeholder)
        # In a real implementation, you would generate PDF/CSV/JSON here
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
    @action(detail=False, methods=["get"], url_path="audit-log")
    def audit_log(self, request):
        """Get audit log for medical records (admin only)"""
        if request.user.user_type != "admin":
            raise PermissionDenied("Only admins can access audit logs")

        # Validate audit parameters
        audit_serializer = MedicalRecordAuditSerializer(data=request.query_params)
        audit_serializer.is_valid(raise_exception=True)

        # Get audit logs (placeholder)
        # In a real implementation, you would query an audit log table
        audit_data = {
            "query": audit_serializer.validated_data,
            "logs": [],  # Placeholder for actual audit logs
            "total_entries": 0,
        }

        return APIResponse.success(message="Audit log retrieved", data=audit_data)
