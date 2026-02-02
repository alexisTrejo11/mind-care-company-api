from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta

from .models import MedicalRecord
from apps.appointments.models import Appointment
from django.core.exceptions import ValidationError, ObjectDoesNotExist

User = get_user_model()


class MedicalRecordSerializer(serializers.ModelSerializer):
    """Base serializer for medical records (read-only)"""

    patient_id = serializers.IntegerField(source="patient.id", read_only=True)
    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)

    specialist_id = serializers.IntegerField(source="specialist.id", read_only=True)
    specialist_name = serializers.CharField(
        source="specialist.user.get_full_name", read_only=True
    )

    appointment_id = serializers.IntegerField(source="appointment.id", read_only=True)
    appointment_date = serializers.DateTimeField(
        source="appointment.appointment_date", read_only=True
    )

    confidentiality_display = serializers.CharField(
        source="get_confidentiality_level_display", read_only=True
    )

    class Meta:
        model = MedicalRecord
        fields = [
            "id",
            "patient_id",
            "patient_name",
            "specialist_id",
            "specialist_name",
            "appointment_id",
            "appointment_date",
            "diagnosis",
            "prescription",
            "notes",
            "recommendations",
            "follow_up_date",
            "confidentiality_level",
            "confidentiality_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields  # All fields are read-only in base serializer


class MedicalRecordCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating medical records (write-only)"""

    appointment_id = serializers.IntegerField(required=True)

    class Meta:
        model = MedicalRecord
        fields = [
            "appointment_id",
            "diagnosis",
            "prescription",
            "notes",
            "recommendations",
            "follow_up_date",
            "confidentiality_level",
        ]
        extra_kwargs = {
            "diagnosis": {"required": True},
            "confidentiality_level": {"default": "standard"},
        }

    def validate_appointment_id(self, value):
        """Validate appointment exists"""
        try:
            appointment = Appointment.objects.get(id=value)
        except Appointment.DoesNotExist:
            raise ValidationError(message="Appointment does not exist")

        return value

    def validate_diagnosis(self, value):
        """Basic format validation"""
        if not value or len(value.strip()) < 10:
            raise ValidationError(
                message="Diagnosis must be at least 10 characters long"
            )
        return value.strip()

    def validate_prescription(self, value):
        """Basic prescription validation"""
        if value and len(value.strip()) < 5:
            raise ValidationError(
                message="Prescription must be at least 5 characters long if provided"
            )
        return value.strip() if value else ""

    def validate_notes(self, value):
        """Basic notes validation"""
        if value and len(value.strip()) < 5:
            raise ValidationError(
                message="Notes must be at least 5 characters long if provided"
            )
        return value.strip() if value else ""

    def validate_follow_up_date(self, value):
        """Basic follow-up date validation"""
        if value and value < timezone.now().date():
            raise ValidationError(message="Follow-up date cannot be in the past")
        return value


class MedicalRecordUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating medical records"""

    class Meta:
        model = MedicalRecord
        fields = [
            "diagnosis",
            "prescription",
            "notes",
            "recommendations",
            "follow_up_date",
        ]

    def validate_diagnosis(self, value):
        if not value or len(value.strip()) < 10:
            raise ValidationError(
                message="Diagnosis must be at least 10 characters long"
            )
        return value.strip()

    def validate_follow_up_date(self, value):
        if value and value < timezone.now().date():
            raise ValidationError(message="Follow-up date cannot be in the past")
        return value


class MedicalRecordFilterSerializer(serializers.Serializer):
    """Serializer for filtering medical records (data format only)"""

    patient_id = serializers.IntegerField(required=False)
    specialist_id = serializers.IntegerField(required=False)
    appointment_id = serializers.IntegerField(required=False)
    confidentiality_level = serializers.ChoiceField(
        choices=MedicalRecord.CONFIDENTIALITY_CHOICES, required=False
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    has_follow_up = serializers.BooleanField(required=False)
    search = serializers.CharField(required=False, max_length=100)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)
    ordering = serializers.ChoiceField(
        choices=["created_at", "-created_at", "follow_up_date", "-follow_up_date"],
        required=False,
        default="-created_at",
    )


class MedicalRecordExportSerializer(serializers.Serializer):
    """Serializer for export parameters (data format only)"""

    format = serializers.ChoiceField(choices=["pdf", "csv", "json"], default="pdf")
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    include_prescriptions = serializers.BooleanField(default=True)
    include_notes = serializers.BooleanField(default=True)
    patient_id = serializers.IntegerField(required=False)

    def validate(self, data):
        if data["start_date"] > data["end_date"]:
            raise ValidationError(message="Start date must be before end date")
        return data


class MedicalRecordAuditSerializer(serializers.Serializer):
    """Serializer for audit log queries (data format only)"""

    patient_id = serializers.IntegerField(required=False)
    specialist_id = serializers.IntegerField(required=False)
    action = serializers.ChoiceField(
        choices=["view", "create", "update", "export"], required=False
    )
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)

    def validate(self, data):
        if data.get("start_date") and data.get("end_date"):
            if data["start_date"] > data["end_date"]:
                raise ValidationError(message="Start date must be before end date")
        return data
