from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, F
from django.core.exceptions import PermissionDenied

from .models import MedicalRecord
from apps.appointments.models import Appointment
from core.exceptions.base_exceptions import (
    BusinessRuleError,
    ValidationError,
    NotFoundError,
    AuthorizationError,
)
from django.db.models.functions import Length
from django.db.models import Avg


class MedicalRecordService:
    """Service layer for medical record business logic"""

    # Edit window for specialists (24 hours)
    EDIT_WINDOW_HOURS = 24

    # Minimum diagnosis length
    MIN_DIAGNOSIS_LENGTH = 10

    # Confidentiality access levels
    CONFIDENTIALITY_LEVELS = {"standard": 1, "sensitive": 2, "highly_sensitive": 3}

    @staticmethod
    def can_access_record(user, medical_record):
        """Check if user can access medical record"""
        if not user or not user.is_authenticated:
            return False

        # Admin can access everything
        if user.user_type == "admin":
            return True

        # Patient can access their own records
        if user.user_type == "patient" and medical_record.patient == user:
            # Patients can't access highly sensitive records
            if medical_record.confidentiality_level == "highly_sensitive":
                return False
            return True

        # Specialist can access records they created
        if user.user_type == "specialist":
            if hasattr(user, "specialist_profile"):
                if medical_record.specialist == user.specialist_profile:
                    return True

        # Staff can access standard records only
        if user.user_type == "staff":
            return medical_record.confidentiality_level == "standard"

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
        """Check if user can delete medical record"""
        # Medical records should rarely be deleted (HIPAA compliance)
        # Only admins can delete, and only with audit trail
        return user.user_type == "admin"

    @staticmethod
    def validate_record_creation(user, appointment):
        """Validate if medical record can be created"""
        if not user or not user.is_authenticated:
            raise AuthorizationError(detail="Authentication required")

        # Check if appointment is completed
        if appointment.status != "completed":
            raise BusinessRuleError(
                detail="Medical records can only be created for completed appointments"
            )

        # Check if record already exists
        if MedicalRecord.objects.filter(appointment=appointment).exists():
            raise BusinessRuleError(
                detail="Medical record already exists for this appointment"
            )

        # Check if user is the treating specialist
        if user.user_type == "specialist":
            if not hasattr(user, "specialist_profile"):
                raise ValidationError(detail="Specialist profile not found")

            if appointment.specialist != user.specialist_profile:
                raise AuthorizationError(
                    detail="You can only create records for your own appointments"
                )

        # Admin can create records for any completed appointment
        elif user.user_type != "admin":
            raise AuthorizationError(
                detail="Only specialists or admins can create medical records"
            )

    @staticmethod
    def validate_diagnosis_content(diagnosis):
        """Validate diagnosis content"""
        if len(diagnosis.strip()) < MedicalRecordService.MIN_DIAGNOSIS_LENGTH:
            raise ValidationError(
                detail=f"Diagnosis must be at least {MedicalRecordService.MIN_DIAGNOSIS_LENGTH} characters"
            )

        # Check for required elements in diagnosis
        required_keywords = ["diagnosis", "assessment", "findings"]
        has_keyword = any(keyword in diagnosis.lower() for keyword in required_keywords)
        if not has_keyword:
            raise BusinessRuleError(detail="Diagnosis must include assessment findings")

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
                raise BusinessRuleError(
                    detail=f"Dangerous drug combination detected: {drug1} and {drug2}"
                )

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

        appointment_id = validated_data.pop("appointment_id")

        try:
            appointment = Appointment.objects.select_related(
                "patient", "specialist"
            ).get(id=appointment_id)
        except Appointment.DoesNotExist:
            raise NotFoundError(detail="Appointment not found")

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

        # Log creation (placeholder for audit service)
        # MedicalRecordAuditService.log_creation(medical_record, user)

        return medical_record

    @classmethod
    @transaction.atomic
    def update_medical_record(cls, user, medical_record, **validated_data):
        """Update medical record with business logic validation"""

        # Check permissions
        if not cls.can_edit_record(user, medical_record):
            raise AuthorizationError(
                detail="You do not have permission to edit this record"
            )

        # Extract data
        diagnosis = validated_data.get("diagnosis")
        prescription = validated_data.get("prescription")
        follow_up_date = validated_data.get("follow_up_date")

        # Apply business logic validation if fields are being updated
        if diagnosis:
            diagnosis = cls.validate_diagnosis_content(diagnosis)
            medical_record.diagnosis = diagnosis

        if prescription is not None:  # Could be empty string
            prescription = cls.validate_prescription_content(prescription)
            medical_record.prescription = prescription

        if follow_up_date is not None:  # Could be None
            follow_up_date = cls.validate_follow_up_date(
                follow_up_date, medical_record.appointment.appointment_date
            )
            medical_record.follow_up_date = follow_up_date

        # Update other fields
        if "notes" in validated_data:
            medical_record.notes = validated_data["notes"]

        if "recommendations" in validated_data:
            medical_record.recommendations = validated_data["recommendations"]

        medical_record.save()

        # Log update (placeholder for audit service)
        # MedicalRecordAuditService.log_update(medical_record, user)

        return medical_record

    @classmethod
    @transaction.atomic
    def delete_medical_record(cls, user, medical_record):
        """Delete medical record (admin only with audit trail)"""

        # Check permissions
        if not cls.can_delete_record(user, medical_record):
            raise AuthorizationError(detail="Only admins can delete medical records")

        # Create audit log before deletion
        # MedicalRecordAuditService.log_deletion(medical_record, user)

        # Actually delete (consider soft delete instead)
        medical_record.delete()

    @classmethod
    def get_filtered_records(cls, user, filters):
        """Get medical records with filters and access control"""
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
        # Permission check
        if user.user_type not in ["admin", "staff", "specialist"]:
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
