"""
Business logic service for medical records with HIPAA compliance
"""

import logging
from typing import Optional, Dict, Any, List, Tuple, BinaryIO
from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count
from django.core.exceptions import ValidationError as DjangoValidationError

from core.exceptions.base_exceptions import (
    ValidationError,
    NotFoundError,
    AuthorizationError,
    PrivacyError,
    BusinessRuleError,
)

from ..models import MedicalRecord
from apps.appointments.models import Appointment
from apps.users.models import User
from apps.specialists.models import Specialist

logger = logging.getLogger(__name__)


class MedicalRecordService:
    """Main service for medical record operations with HIPAA compliance"""

    @staticmethod
    @transaction.atomic
    def create_medical_record(
        appointment_id: int,
        diagnosis: str,
        confidentiality_level: str = "standard",
        **kwargs,
    ) -> MedicalRecord:
        """
        Create a new medical record with HIPAA compliance checks
        """
        try:
            # Get appointment
            appointment = Appointment.objects.select_related(
                "patient", "specialist"
            ).get(id=appointment_id)

            # Validate appointment status
            if appointment.status != "completed":
                raise BusinessRuleError(
                    detail="Medical records can only be created for completed appointments",
                    code="appointment_not_completed",
                )

            # Check if record already exists
            if MedicalRecord.objects.filter(appointment=appointment).exists():
                raise BusinessRuleError(
                    detail="Medical record already exists for this appointment",
                    code="duplicate_record",
                )

            # Create medical record
            record = MedicalRecord.objects.create(
                patient=appointment.patient,
                specialist=appointment.specialist,
                appointment=appointment,
                diagnosis=diagnosis,
                confidentiality_level=confidentiality_level,
                **kwargs,
            )

            # Log creation for audit trail
            logger.info(
                f"Medical record created: {record.id} - "
                f"Patient: {appointment.patient.email}, "
                f"Specialist: {appointment.specialist.user.email}, "
                f"Confidentiality: {confidentiality_level}"
            )

            # Create audit log entry
            MedicalRecordService._create_audit_log(
                action="create",
                record=record,
                user=None,  # Will be set by view context
                metadata={"diagnosis_length": len(diagnosis)},
            )

            return record

        except Appointment.DoesNotExist:
            raise NotFoundError(detail="Appointment not found")
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e))

    @staticmethod
    @transaction.atomic
    def update_medical_record(
        record_id: int, user: User, **update_data
    ) -> MedicalRecord:
        """
        Update medical record with access control and audit trail
        """
        try:
            record = MedicalRecord.objects.select_related(
                "patient", "specialist", "specialist__user"
            ).get(id=record_id)

            # Check access permissions
            MedicalRecordService._check_update_permission(record, user)

            # Track changes for audit
            changes = {}
            for field, new_value in update_data.items():
                old_value = getattr(record, field, None)
                if old_value != new_value:
                    changes[field] = {
                        "old": str(old_value)[:100] if old_value else None,
                        "new": str(new_value)[:100] if new_value else None,
                    }

            # Update fields
            for field, value in update_data.items():
                setattr(record, field, value)

            record.full_clean()
            record.save()

            # Log update for audit trail
            if changes:
                MedicalRecordService._create_audit_log(
                    action="update",
                    record=record,
                    user=user,
                    metadata={"changes": changes},
                )

            logger.info(f"Medical record updated: {record.id}")

            return record

        except MedicalRecord.DoesNotExist:
            raise NotFoundError(detail="Medical record not found")
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e))

    @staticmethod
    def get_medical_record(
        record_id: int, user: User
    ) -> Tuple[MedicalRecord, Dict[str, Any]]:
        """
        Get medical record with access control and audit logging
        """
        try:
            record = MedicalRecord.objects.select_related(
                "patient", "specialist", "specialist__user", "appointment"
            ).get(id=record_id)

            # Check access permissions
            MedicalRecordService._check_view_permission(record, user)

            # Log access for audit trail
            MedicalRecordService._create_audit_log(
                action="view", record=record, user=user, metadata={}
            )

            # Calculate metadata
            metadata = MedicalRecordService._get_record_metadata(record, user)

            return record, metadata

        except MedicalRecord.DoesNotExist:
            raise NotFoundError(detail="Medical record not found")

    @staticmethod
    def search_medical_records(
        filters: Dict[str, Any], user: User, page: int = 1, page_size: int = 20
    ) -> Tuple[List[MedicalRecord], Dict[str, Any]]:
        """
        Search medical records with role-based filtering and access control
        """
        try:
            # Start with base queryset
            queryset = MedicalRecord.objects.select_related(
                "patient", "specialist", "specialist__user", "appointment"
            )

            # Apply role-based filtering
            queryset = MedicalRecordService._apply_role_filtering(queryset, user)

            # Apply user-provided filters
            if patient_id := filters.get("patient_id"):
                queryset = queryset.filter(patient__user_id=patient_id)

            if specialist_id := filters.get("specialist_id"):
                queryset = queryset.filter(specialist_id=specialist_id)

            if appointment_id := filters.get("appointment_id"):
                queryset = queryset.filter(appointment_id=appointment_id)

            if confidentiality_level := filters.get("confidentiality_level"):
                queryset = queryset.filter(confidentiality_level=confidentiality_level)

            # Date range filtering
            if start_date := filters.get("start_date"):
                queryset = queryset.filter(created_at__date__gte=start_date)

            if end_date := filters.get("end_date"):
                queryset = queryset.filter(created_at__date__lte=end_date)

            # Follow-up filtering
            if has_follow_up := filters.get("has_follow_up"):
                if has_follow_up:
                    queryset = queryset.filter(follow_up_date__isnull=False)
                else:
                    queryset = queryset.filter(follow_up_date__isnull=True)

            # Search by text
            if search_query := filters.get("search"):
                queryset = queryset.filter(
                    Q(diagnosis__icontains=search_query)
                    | Q(prescription__icontains=search_query)
                    | Q(notes__icontains=search_query)
                    | Q(recommendations__icontains=search_query)
                    | Q(patient__first_name__icontains=search_query)
                    | Q(patient__last_name__icontains=search_query)
                )

            # Ordering
            ordering = filters.get("ordering", "-created_at")
            queryset = queryset.order_by(ordering)

            # Pagination
            total = queryset.count()
            start = (page - 1) * page_size
            end = start + page_size

            records = queryset[start:end]

            # Pagination metadata
            pagination = {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
                "has_next": end < total,
                "has_previous": page > 1,
            }

            return list(records), pagination

        except Exception as e:
            logger.error(f"Error searching medical records: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def get_patient_records_summary(patient_id: str, user: User) -> Dict[str, Any]:
        """
        Get summary of patient's medical records
        """
        try:
            # Verify access
            patient = User.objects.get(user_id=patient_id, user_type="patient")

            # Patients can only see their own records
            if user.user_type == "patient" and user != patient:
                raise AuthorizationError(
                    detail="Cannot access another patient's records",
                    code="unauthorized_patient_access",
                )

            # Get records with confidentiality filtering
            records = MedicalRecord.objects.filter(patient=patient)
            records = MedicalRecordService._apply_role_filtering(records, user)

            # Calculate statistics
            total_records = records.count()

            confidentiality_distribution = (
                records.values("confidentiality_level")
                .annotate(count=Count("id"))
                .order_by("confidentiality_level")
            )

            # Get most recent diagnosis
            recent_record = records.order_by("-created_at").first()

            # Count upcoming follow-ups
            upcoming_follow_ups = records.filter(
                follow_up_date__gte=timezone.now().date(),
                follow_up_date__lte=timezone.now().date() + timedelta(days=30),
            ).count()

            # Get specialists who have treated this patient
            treating_specialists = (
                records.values(
                    "specialist__user__first_name",
                    "specialist__user__last_name",
                    "specialist__specialization",
                )
                .distinct()
                .order_by("specialist__user__last_name")
            )

            return {
                "patient": {
                    "id": patient.id,
                    "name": patient.get_full_name(),
                    "email": patient.email,
                },
                "statistics": {
                    "total_records": total_records,
                    "confidentiality_distribution": list(confidentiality_distribution),
                    "upcoming_follow_ups": upcoming_follow_ups,
                    "treating_specialists_count": len(treating_specialists),
                },
                "recent_diagnosis": (
                    recent_record.diagnosis[:200] if recent_record else None
                ),
                "treating_specialists": list(treating_specialists),
                "has_records": total_records > 0,
            }

        except User.DoesNotExist:
            raise NotFoundError(detail="Patient not found")

    @staticmethod
    def get_specialist_records_summary(
        specialist_id: int, user: User
    ) -> Dict[str, Any]:
        """
        Get summary of specialist's medical records
        """
        try:
            specialist = Specialist.objects.get(id=specialist_id)

            # Verify access
            if user.user_type == "specialist":
                if not hasattr(user, "specialist_profile"):
                    raise AuthorizationError(
                        detail="Specialist profile not found",
                        code="specialist_profile_missing",
                    )
                if user.specialist_profile != specialist:
                    raise AuthorizationError(
                        detail="Cannot access another specialist's records",
                        code="unauthorized_specialist_access",
                    )

            # Get records
            records = MedicalRecord.objects.filter(specialist=specialist)

            # Calculate statistics
            total_records = records.count()

            # Records by confidentiality
            confidentiality_stats = (
                records.values("confidentiality_level")
                .annotate(count=Count("id"))
                .order_by("confidentiality_level")
            )

            # Recent activity
            recent_activity = records.order_by("-updated_at")[:5]

            # Most common diagnoses (simplified)
            # In production, you might want to use ICD-10 codes

            return {
                "specialist": {
                    "id": specialist.id,
                    "name": specialist.user.get_full_name(),
                    "specialization": specialist.specialization,
                },
                "statistics": {
                    "total_records": total_records,
                    "confidentiality_stats": list(confidentiality_stats),
                    "records_last_30_days": records.filter(
                        created_at__gte=timezone.now() - timedelta(days=30)
                    ).count(),
                },
                "recent_activity": [
                    {
                        "patient_name": r.patient.get_full_name(),
                        "diagnosis": r.diagnosis[:100],
                        "date": r.created_at.date().isoformat(),
                    }
                    for r in recent_activity
                ],
            }

        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")

    # ========== PRIVATE HELPER METHODS ==========

    @staticmethod
    def _check_view_permission(record: MedicalRecord, user: User) -> None:
        """Check if user can view this medical record"""
        from .privacy_service import PrivacyService

        PrivacyService.check_record_access(record, user, "view")

    @staticmethod
    def _check_update_permission(record: MedicalRecord, user: User) -> None:
        """Check if user can update this medical record"""
        from .privacy_service import PrivacyService

        PrivacyService.check_record_access(record, user, "update")

        # Additional update constraints
        edit_window = record.created_at + timedelta(hours=24)

        if user.user_type == "specialist":
            if timezone.now() > edit_window:
                raise AuthorizationError(
                    detail="Medical records can only be edited within 24 hours of creation",
                    code="edit_window_expired",
                )

    @staticmethod
    def _apply_role_filtering(queryset, user: User):
        """Apply role-based filtering to medical records queryset"""
        from .privacy_service import PrivacyService

        if user.user_type == "patient":
            # Patients can only see their own records
            return queryset.filter(patient=user)

        elif user.user_type == "specialist":
            # Specialists can see records they created
            if hasattr(user, "specialist_profile"):
                return queryset.filter(specialist=user.specialist_profile)
            return queryset.none()

        elif user.user_type == "staff":
            # Staff can see standard and sensitive records
            return queryset.exclude(confidentiality_level="highly_sensitive")

        elif user.user_type == "admin":
            # Admins can see all records
            return queryset

        # Default: no access
        return queryset.none()

    @staticmethod
    def _get_record_metadata(record: MedicalRecord, user: User) -> Dict[str, Any]:
        """Get metadata about a medical record"""
        metadata = {
            "access_level": user.user_type,
            "can_edit": False,
            "can_delete": False,
            "is_owner": False,
        }

        # Check edit permissions
        edit_window = record.created_at + timedelta(hours=24)

        if user.user_type == "specialist":
            if hasattr(user, "specialist_profile"):
                metadata["is_owner"] = user.specialist_profile == record.specialist
                metadata["can_edit"] = (
                    metadata["is_owner"] and timezone.now() < edit_window
                )

        elif user.user_type == "admin":
            metadata["can_edit"] = True
            metadata["can_delete"] = True

        # Check if follow-up is upcoming
        if record.follow_up_date:
            today = timezone.now().date()
            metadata["follow_up_status"] = (
                "upcoming" if record.follow_up_date >= today else "past"
            )
            metadata["days_until_follow_up"] = (
                (record.follow_up_date - today).days
                if record.follow_up_date >= today
                else None
            )

        return metadata

    @staticmethod
    def _create_audit_log(
        action: str,
        record: MedicalRecord,
        user: Optional[User],
        metadata: Dict[str, Any],
    ) -> None:
        """
        Create audit log entry for medical record access
        In production, this would write to a dedicated audit log table
        """
        audit_data = {
            "timestamp": timezone.now().isoformat(),
            "action": action,
            "record_id": record.id,
            "patient_id": str(record.patient.id),
            "confidentiality_level": record.confidentiality_level,
            "user_id": str(user.id) if user else "system",
            "user_type": user.user_type if user else "system",
            "metadata": metadata,
        }

        logger.info(
            f"Medical Record Audit: {action.upper()} - "
            f'Record: {record.id}, User: {user.email if user else "system"}',
            extra={"audit_data": audit_data},
        )

        # In production, save to database:
        # from ..models import MedicalRecordAuditLog
        # MedicalRecordAuditLog.objects.create(**audit_data)
        pass
