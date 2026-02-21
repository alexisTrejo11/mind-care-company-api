import logging
from datetime import timedelta
from django.db.models.manager import BaseManager
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, F

from .models import MedicalRecord
from apps.appointments.models import Appointment
from apps.core.exceptions.base_exceptions import (
    BusinessRuleError,
    PrivacyError,
    ValidationError,
    NotFoundError,
    AuthorizationError,
)
from django.db.models.functions import Length
from django.db.models import Avg

logger = logging.getLogger(__name__)


class MedicalRecordService:
    """Service layer for medical record business logic"""

    EDIT_WINDOW_HOURS = 24
    MIN_DIAGNOSIS_LENGTH = 10
    CONFIDENTIALITY_LEVELS = {"standard": 1, "sensitive": 2, "highly_sensitive": 3}

    @staticmethod
    def can_access_record(user, medical_record):
        """Check if user can access medical record"""
        if not user or not user.is_authenticated:
            logger.info(
                f"Access denied to medical record {medical_record.id}: User not authenticated"
            )
            return False

        # Admin can access everything
        if user.user_type == "admin":
            logger.info(
                f"Admin {user.email} accessing medical record {medical_record.id}"
            )
            return True

        # Patient can access their own records
        if user.user_type == "patient" and medical_record.patient == user:
            # Patients can't access highly sensitive records
            if medical_record.confidentiality_level == "highly_sensitive":
                logger.info(
                    f"Patient {user.email} denied access to highly sensitive record {medical_record.id}"
                )
                return False
            logger.info(
                f"Patient {user.email} accessing own medical record {medical_record.id}"
            )
            return True

        # Specialist can access records they created
        if user.user_type == "specialist":
            if hasattr(user, "specialist_profile"):
                if medical_record.specialist == user.specialist_profile:
                    logger.info(
                        f"Specialist {user.email} accessing their medical record {medical_record.id}"
                    )
                    return True

        # Staff can access standard records only
        if user.user_type == "staff":
            can_access = medical_record.confidentiality_level == "standard"
            if can_access:
                logger.info(
                    f"Staff {user.email} accessing standard medical record {medical_record.id}"
                )
            else:
                logger.info(
                    f"Staff {user.email} denied access to non-standard record {medical_record.id}"
                )
            return can_access

        logger.info(
            f"User {user.email} ({user.user_type}) denied access to medical record {medical_record.id}"
        )
        return False

    @staticmethod
    def can_edit_record(user, medical_record):
        """Check if user can edit medical record"""
        if not MedicalRecordService.can_access_record(user, medical_record):
            return False

        # Admin can always edit
        if user.user_type == "admin":
            return True

        # Specialist can edit within edit window
        if user.user_type == "specialist":
            if hasattr(user, "specialist_profile"):
                if medical_record.specialist == user.specialist_profile:
                    edit_window = medical_record.created_at + timedelta(
                        hours=MedicalRecordService.EDIT_WINDOW_HOURS
                    )
                    return timezone.now() < edit_window

        return False

    @staticmethod
    def can_delete_record(user, medical_record):
        today = timezone.now().date()

        # Can only delete if created today
        if medical_record.created_at.date() > today:
            return False

        return user.user_type == "admin"

    @staticmethod
    def validate_record_creation(user, appointment):
        """Validate if medical record can be created"""
        if not user or not user.is_authenticated:
            logger.warning(
                f"Unauthenticated attempt to create medical record for appointment {appointment.id}"
            )
            raise AuthorizationError(detail="Authentication required")

        if not appointment:
            logger.error("Appointment not provided for medical record creation")
            raise ValidationError(detail="Appointment must be provided")

        if appointment.status != "completed":
            logger.warning(
                f"Attempt to create medical record for non-completed appointment {appointment.id} (status: {appointment.status})"
            )
            raise BusinessRuleError(
                detail="Medical records can only be created for completed appointments"
            )

        if MedicalRecord.objects.filter(appointment=appointment).exists():
            logger.warning(
                f"Attempt to create duplicate medical record for appointment {appointment.id}"
            )
            raise BusinessRuleError(
                detail="Medical record already exists for this appointment"
            )

        if user.user_type == "specialist":
            if not hasattr(user, "specialist_profile"):
                logger.error(
                    f"User {user.email} marked as specialist but has no profile"
                )
                raise ValidationError(detail="Specialist profile not found")

            if appointment.specialist != user.specialist_profile:
                logger.warning(
                    f"Specialist {user.email} attempted to create record for another specialist's appointment {appointment.id}"
                )
                raise AuthorizationError(
                    detail="You can only create records for your own appointments"
                )
        elif user.user_type != "admin":
            logger.warning(
                f"User {user.email} ({user.user_type}) unauthorized to create medical records"
            )
            raise AuthorizationError(
                detail="Only specialists or admins can create medical records"
            )

    @staticmethod
    def validate_diagnosis_content(diagnosis):
        """Validate diagnosis content"""
        if len(diagnosis.strip()) < MedicalRecordService.MIN_DIAGNOSIS_LENGTH:
            logger.warning(
                f"Diagnosis validation failed: too short ({len(diagnosis.strip())} chars)"
            )
            raise ValidationError(
                detail=f"Diagnosis must be at least {MedicalRecordService.MIN_DIAGNOSIS_LENGTH} characters"
            )

        # Check for required elements in diagnosis
        required_keywords = ["diagnosis", "assessment", "findings"]
        has_keyword = any(keyword in diagnosis.lower() for keyword in required_keywords)
        if not has_keyword:
            logger.warning(
                "Diagnosis validation failed: missing required assessment keywords"
            )
            raise BusinessRuleError(detail="Diagnosis must include assessment findings")

        logger.info("Diagnosis content validated successfully")
        return diagnosis

    @staticmethod
    def validate_prescription_content(prescription):
        """Validate prescription content"""
        if not prescription:
            return ""

        # Check for dangerous combinations
        dangerous_combinations = [
            ("opioid", "benzodiazepine"),
            ("MAOI", "SSRI"),
            ("warfarin", "aspirin"),
        ]

        prescription_lower = prescription.lower()
        for drug1, drug2 in dangerous_combinations:
            if drug1 in prescription_lower and drug2 in prescription_lower:
                logger.warning(
                    f"Dangerous drug combination detected: {drug1} and {drug2}"
                )
                raise BusinessRuleError(
                    detail=f"Dangerous drug combination detected: {drug1} and {drug2}"
                )

        logger.info("Prescription validated successfully")
        return prescription

    @staticmethod
    def validate_follow_up_date(follow_up_date, appointment_date):
        """Validate follow-up date"""
        if not follow_up_date:
            return None

        if follow_up_date <= appointment_date.date():
            raise ValidationError(
                detail="Follow-up date must be after appointment date"
            )

        # Minimum 1 day after appointment
        min_follow_up = appointment_date.date() + timedelta(days=1)
        if follow_up_date < min_follow_up:
            raise ValidationError(
                detail="Follow-up must be at least 1 day after appointment"
            )

        # Maximum 1 year after appointment
        max_follow_up = appointment_date.date() + timedelta(days=365)
        if follow_up_date > max_follow_up:
            raise ValidationError(
                detail="Follow-up cannot be more than 1 year after appointment"
            )

        return follow_up_date

    @staticmethod
    def validate_confidentiality_level(level, diagnosis_content):
        """Validate confidentiality level based on content"""
        highly_sensitive_keywords = [
            "hiv",
            "aids",
            "mental health",
            "psychiatric",
            "substance abuse",
            "addiction",
            "suicide",
        ]

        diagnosis_lower = diagnosis_content.lower()

        if level == "highly_sensitive":
            # Verify content justifies high confidentiality
            has_sensitive_content = any(
                keyword in diagnosis_lower for keyword in highly_sensitive_keywords
            )
            if not has_sensitive_content:
                raise BusinessRuleError(
                    detail="Highly sensitive level requires sensitive health information"
                )

        return level

    @classmethod
    @transaction.atomic
    def create_medical_record(cls, user, **validated_data):
        """Create a new medical record with business logic validation"""
        appointment = validated_data.get("appointment")
        if not appointment:
            raise ValidationError(detail="Appointment must be provided")

        # Validate creation permissions
        cls.validate_record_creation(user, appointment)

        # Extract data
        diagnosis = validated_data.get("diagnosis")
        prescription = validated_data.get("prescription", "")
        follow_up_date = validated_data.get("follow_up_date")
        confidentiality_level = validated_data.get("confidentiality_level", "standard")

        # Apply business logic validation
        diagnosis = cls.validate_diagnosis_content(diagnosis)
        prescription = cls.validate_prescription_content(prescription)

        # Validate follow-up date
        follow_up_date = cls.validate_follow_up_date(
            follow_up_date, appointment.appointment_date
        )

        # Validate confidentiality level
        confidentiality_level = cls.validate_confidentiality_level(
            confidentiality_level, diagnosis
        )

        # Create medical record
        medical_record = MedicalRecord.objects.create(
            patient=appointment.patient,
            specialist=appointment.specialist,
            appointment=appointment,
            diagnosis=diagnosis,
            prescription=prescription,
            notes=validated_data.get("notes", ""),
            recommendations=validated_data.get("recommendations", ""),
            follow_up_date=follow_up_date,
            confidentiality_level=confidentiality_level,
        )

        logger.info(
            f"Medical record {medical_record.id} created successfully by {user.email} "
            f"for patient {appointment.patient.email}, appointment {appointment.id}, "
            f"confidentiality: {confidentiality_level}"
        )

        return medical_record

    @classmethod
    @transaction.atomic
    def update_medical_record(cls, user, medical_record, **validated_data):
        """Update medical record with business logic validation"""
        logger.info(
            f"User {user.email} attempting to update medical record {medical_record.id}"
        )

        # Check permissions
        if not cls.can_edit_record(user, medical_record):
            logger.warning(
                f"User {user.email} denied permission to edit medical record {medical_record.id}"
            )
            raise AuthorizationError(
                detail="You do not have permission to edit this record"
            )

        # Extract data
        diagnosis = validated_data.get("diagnosis")
        prescription = validated_data.get("prescription")
        follow_up_date = validated_data.get("follow_up_date")

        updated_fields = []
        if diagnosis:
            diagnosis = cls.validate_diagnosis_content(diagnosis)
            medical_record.diagnosis = diagnosis
            updated_fields.append("diagnosis")

        if prescription is not None:  # Could be empty string
            prescription = cls.validate_prescription_content(prescription)
            medical_record.prescription = prescription
            updated_fields.append("prescription")

        if follow_up_date is not None:  # Could be None
            follow_up_date = cls.validate_follow_up_date(
                follow_up_date, medical_record.appointment.appointment_date
            )
            medical_record.follow_up_date = follow_up_date
            updated_fields.append("follow_up_date")

        # Update other fields
        if "notes" in validated_data:
            medical_record.notes = validated_data["notes"]
            updated_fields.append("notes")

        if "recommendations" in validated_data:
            medical_record.recommendations = validated_data["recommendations"]
            updated_fields.append("recommendations")

        medical_record.save(update_fields=updated_fields)

        logger.info(
            f"Medical record {medical_record.id} updated by {user.email}. "
            f"Updated fields: {', '.join(updated_fields) if updated_fields else 'none'}"
        )

        return medical_record

    @classmethod
    @transaction.atomic
    def delete_medical_record(cls, user, medical_record):
        """Delete medical record (admin only with audit trail)"""
        logger.info(
            f"User {user.email} attempting to delete medical record {medical_record.id}"
        )

        # Check permissions
        if not cls.can_delete_record(user, medical_record):
            logger.warning(
                f"User {user.email} denied permission to delete medical record {medical_record.id}"
            )
            raise PrivacyError(detail="Only admins can delete medical records")

        # Log deletion details before deleting
        logger.info(
            f"Deleting medical record {medical_record.id} by admin {user.email}. "
            f"Patient: {medical_record.patient.email}, Appointment: {medical_record.appointment.id}, "
            f"Confidentiality: {medical_record.confidentiality_level}"
        )

        # Actually delete (consider soft delete instead)
        medical_record.delete()
        logger.info(f"Medical record {medical_record.id} deleted successfully")

    @classmethod
    def get_filtered_records(cls, user, filters={}) -> BaseManager[MedicalRecord]:
        """Get medical records with filters and access control"""
        if not user or not user.is_authenticated:
            return MedicalRecord.objects.none()

        queryset = MedicalRecord.objects.select_related(
            "patient", "specialist", "specialist__user", "appointment"
        )

        # Apply access control
        if user.user_type == "patient":
            queryset = queryset.filter(patient=user)
            # Patients can't see highly sensitive records
            queryset = queryset.exclude(confidentiality_level="highly_sensitive")

        elif user.user_type == "specialist":
            if hasattr(user, "specialist_profile"):
                queryset = queryset.filter(specialist=user.specialist_profile)

        elif user.user_type == "staff":
            # Staff can only see standard records
            queryset = queryset.filter(confidentiality_level="standard")

        # Apply filters
        patient_id = filters.get("patient_id")
        if patient_id:
            # Additional access check for patient_id filter
            if user.user_type == "patient" and user.id != patient_id:
                raise AuthorizationError(
                    detail="Cannot access another patient's records"
                )
            queryset = queryset.filter(patient_id=patient_id)

        specialist_id = filters.get("specialist_id")
        if specialist_id:
            if user.user_type == "specialist":
                if (
                    not hasattr(user, "specialist_profile")
                    or user.specialist_profile.id != specialist_id
                ):
                    raise AuthorizationError(
                        detail="Cannot access another specialist's records"
                    )
            queryset = queryset.filter(specialist_id=specialist_id)

        appointment_id = filters.get("appointment_id")
        if appointment_id:
            queryset = queryset.filter(appointment_id=appointment_id)

        confidentiality_level = filters.get("confidentiality_level")
        if confidentiality_level:
            queryset = queryset.filter(confidentiality_level=confidentiality_level)

        start_date = filters.get("start_date")
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)

        end_date = filters.get("end_date")
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

        has_follow_up = filters.get("has_follow_up")
        if has_follow_up is not None:
            if has_follow_up:
                queryset = queryset.filter(follow_up_date__isnull=False)
            else:
                queryset = queryset.filter(follow_up_date__isnull=True)

        search = filters.get("search")
        if search:
            queryset = queryset.filter(
                Q(diagnosis__icontains=search)
                | Q(prescription__icontains=search)
                | Q(notes__icontains=search)
                | Q(recommendations__icontains=search)
            )

        # Apply ordering
        ordering = filters.get("ordering", "-created_at")
        queryset = queryset.order_by(ordering)

        return queryset

    @classmethod
    def get_statistics(cls, user, period="month"):
        """Get medical record statistics"""
        logger.info(
            f"User {user.email} requesting medical record statistics for period: {period}"
        )

        # Permission check
        if user.user_type not in ["admin", "staff", "specialist"]:
            logger.warning(
                f"User {user.email} ({user.user_type}) unauthorized to view statistics"
            )
            raise AuthorizationError(
                detail="Only admin, staff, or specialists can view statistics"
            )

        # Define date range
        now = timezone.now()
        if period == "today":
            start_date = now.date()
            end_date = now.date()
        elif period == "week":
            start_date = now.date() - timedelta(days=now.weekday())
            end_date = start_date + timedelta(days=6)
        elif period == "month":
            start_date = now.date().replace(day=1)
            if start_date.month == 12:
                end_date = start_date.replace(
                    year=start_date.year + 1, month=1, day=1
                ) - timedelta(days=1)
            else:
                end_date = start_date.replace(
                    month=start_date.month + 1, day=1
                ) - timedelta(days=1)
        else:  # year or custom
            start_date = now.date().replace(month=1, day=1)
            end_date = now.date().replace(month=12, day=31)

        # Base queryset with access control
        queryset = MedicalRecord.objects.all()

        if user.user_type == "specialist":
            if hasattr(user, "specialist_profile"):
                queryset = queryset.filter(specialist=user.specialist_profile)

        # Filter by period
        queryset = queryset.filter(created_at__date__range=[start_date, end_date])

        # Calculate statistics
        total_records = queryset.count()

        if total_records == 0:
            return {
                "period": period,
                "start_date": start_date,
                "end_date": end_date,
                "total_records": 0,
                "message": "No records found for the selected period",
            }

        # Confidentiality distribution
        confidentiality_counts = queryset.values("confidentiality_level").annotate(
            count=Count("id")
        )
        confidentiality_distribution = {
            item["confidentiality_level"]: item["count"]
            for item in confidentiality_counts
        }

        # Records with follow-up
        follow_up_count = queryset.filter(follow_up_date__isnull=False).count()
        follow_up_percentage = (
            (follow_up_count / total_records * 100) if total_records > 0 else 0
        )

        # Average diagnosis length
        avg_diagnosis_length = (
            queryset.annotate(diagnosis_len=Length("diagnosis")).aggregate(
                avg_len=Avg("diagnosis_len")
            )["avg_len"]
            or 0
        )

        # Most common specialists (if admin)
        if user.user_type == "admin":
            specialist_stats = (
                queryset.values(
                    "specialist__user__first_name",
                    "specialist__user__last_name",
                    "specialist__specialization",
                )
                .annotate(record_count=Count("id"))
                .order_by("-record_count")[:5]
            )
        else:
            specialist_stats = []

        logger.info(
            f"Statistics generated for {user.email}: {total_records} records found for period {period} "
            f"({start_date} to {end_date})"
        )

        return {
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_records": total_records,
            "confidentiality_distribution": confidentiality_distribution,
            "follow_up_stats": {
                "with_follow_up": follow_up_count,
                "without_follow_up": total_records - follow_up_count,
                "percentage": round(follow_up_percentage, 2),
            },
            "diagnosis_stats": {"avg_length": round(avg_diagnosis_length, 1)},
            "top_specialists": specialist_stats,
        }
