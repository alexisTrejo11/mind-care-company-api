from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta

from .models import MedicalRecord
from .validators import (
    validate_diagnosis_format,
    validate_prescription_format,
    validate_follow_up_date,
    validate_medical_note_content,
    validate_confidentiality_access,
)
from core.responses.api_response import APIResponse
from apps.appointments.models import Appointment

User = get_user_model()


class MedicalRecordSerializer(serializers.ModelSerializer):
    """Base serializer for medical records"""

    patient_id = serializers.UUIDField(source="patient.user_id", read_only=True)
    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)
    patient_email = serializers.EmailField(source="patient.email", read_only=True)

    specialist_id = serializers.IntegerField(source="specialist.id", read_only=True)
    specialist_name = serializers.CharField(
        source="specialist.user.get_full_name", read_only=True
    )
    specialist_specialization = serializers.CharField(
        source="specialist.specialization", read_only=True
    )

    appointment_id = serializers.IntegerField(source="appointment.id", read_only=True)
    appointment_date = serializers.DateTimeField(
        source="appointment.appointment_date", read_only=True
    )
    appointment_type = serializers.CharField(
        source="appointment.appointment_type", read_only=True
    )

    confidentiality_display = serializers.CharField(
        source="get_confidentiality_level_display", read_only=True
    )

    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = MedicalRecord
        fields = [
            "id",
            "patient_id",
            "patient_name",
            "patient_email",
            "specialist_id",
            "specialist_name",
            "specialist_specialization",
            "appointment_id",
            "appointment_date",
            "appointment_type",
            "diagnosis",
            "prescription",
            "notes",
            "recommendations",
            "follow_up_date",
            "confidentiality_level",
            "confidentiality_display",
            "can_edit",
            "can_delete",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "confidentiality_display",
            "patient_id",
            "patient_name",
            "patient_email",
            "specialist_id",
            "specialist_name",
            "specialist_specialization",
            "appointment_id",
            "appointment_date",
            "appointment_type",
            "can_edit",
            "can_delete",
        ]

    def get_can_edit(self, obj) -> bool:
        """Check if current user can edit this record"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        user = request.user

        # Only the creating specialist can edit (within 24 hours)
        if user.user_type == "specialist":
            if hasattr(user, "specialist_profile"):
                if user.specialist_profile == obj.specialist:
                    # Check if within edit window (24 hours)
                    edit_window = obj.created_at + timedelta(hours=24)
                    return timezone.now() < edit_window

        # Admins can always edit
        return user.user_type == "admin"

    def get_can_delete(self, obj) -> bool:
        """Check if current user can delete this record"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        user = request.user

        # Medical records should rarely be deleted (HIPAA compliance)
        # Only admins can delete, and only with audit trail
        return user.user_type == "admin"

    def validate_diagnosis(self, value):
        validate_diagnosis_format(value)
        return value

    def validate_prescription(self, value):
        validate_prescription_format(value)
        return value

    def validate_notes(self, value):
        validate_medical_note_content(value)
        return value

    def validate_follow_up_date(self, value):
        validate_follow_up_date(value)
        return value

    def validate(self, attrs):
        """Cross-field validation for medical records"""
        # Validate follow-up date is after appointment
        appointment = self.instance.appointment if self.instance else None
        follow_up_date = attrs.get("follow_up_date")

        if follow_up_date and appointment:
            appointment_date = appointment.appointment_date

            if follow_up_date <= appointment_date:
                raise serializers.ValidationError(
                    {"follow_up_date": "Follow-up date must be after appointment date"}
                )

            # Minimum 1 day after appointment
            min_follow_up = appointment_date + timedelta(days=1)
            if follow_up_date < min_follow_up:
                raise serializers.ValidationError(
                    {
                        "follow_up_date": "Follow-up must be at least 1 day after appointment"
                    }
                )

        # Validate allergies if mentioned
        notes = attrs.get("notes", "")
        prescription = attrs.get("prescription", "")

        if notes and prescription:
            from .validators import validate_allergy_information

            try:
                validate_allergy_information(notes, prescription)
            except ValidationError as e:
                raise serializers.ValidationError({"prescription": str(e)})

        return attrs


class MedicalRecordCreateSerializer(MedicalRecordSerializer):
    """Serializer for creating medical records"""

    appointment_id = serializers.IntegerField(write_only=True, required=True)

    class Meta(MedicalRecordSerializer.Meta):
        fields = MedicalRecordSerializer.Meta.fields + ["appointment_id"]
        read_only_fields = [
            f
            for f in MedicalRecordSerializer.Meta.read_only_fields
            if f not in ["appointment_id"]
        ]

    def validate_appointment_id(self, value):
        """Validate appointment exists and is completed"""
        try:
            appointment = Appointment.objects.get(id=value)

            # Check if appointment is completed
            if appointment.status != "completed":
                raise serializers.ValidationError(
                    "Medical records can only be created for completed appointments"
                )

            # Check if record already exists for this appointment
            if hasattr(appointment, "medical_records"):
                if appointment.medical_records.exists():
                    raise serializers.ValidationError(
                        "Medical record already exists for this appointment"
                    )

            return value

        except Appointment.DoesNotExist:
            raise serializers.ValidationError("Appointment not found")

    def validate(self, attrs):
        """Additional validation for record creation"""
        attrs = super().validate(attrs)

        request = self.context.get("request")
        appointment_id = attrs.get("appointment_id")

        if request and appointment_id:
            try:
                appointment = Appointment.objects.get(id=appointment_id)

                # For specialists, verify they were the treating specialist
                if request.user.user_type == "specialist":
                    if not hasattr(request.user, "specialist_profile"):
                        raise serializers.ValidationError(
                            {"specialist": "Specialist profile not found"}
                        )

                    if appointment.specialist != request.user.specialist_profile:
                        raise serializers.ValidationError(
                            {
                                "appointment_id": "You can only create records for your own appointments"
                            }
                        )

                # Set patient and specialist from appointment
                attrs["patient"] = appointment.patient
                attrs["specialist"] = appointment.specialist
                attrs["appointment"] = appointment

            except Appointment.DoesNotExist:
                raise serializers.ValidationError(
                    {"appointment_id": "Appointment not found"}
                )

        return attrs


class MedicalRecordUpdateSerializer(MedicalRecordSerializer):
    """Serializer for updating medical records (restricted)"""

    class Meta(MedicalRecordSerializer.Meta):
        read_only_fields = MedicalRecordSerializer.Meta.read_only_fields + [
            "patient_id",
            "specialist_id",
            "appointment_id",
            "confidentiality_level",
        ]

    def validate(self, attrs):
        """Restrict updates based on time and user role"""
        instance = getattr(self, "instance", None)
        if not instance:
            return attrs

        request = self.context.get("request")
        if not request:
            return attrs

        user = request.user

        # Check if record can be edited
        edit_window = instance.created_at + timedelta(hours=24)

        if timezone.now() > edit_window and user.user_type != "admin":
            raise serializers.ValidationError(
                {
                    "non_field_errors": "Medical record can only be edited within 24 hours of creation"
                }
            )

        # Specialists can only edit their own records
        if user.user_type == "specialist":
            if not hasattr(user, "specialist_profile"):
                raise serializers.ValidationError(
                    {"specialist": "Specialist profile not found"}
                )

            if user.specialist_profile != instance.specialist:
                raise serializers.ValidationError(
                    {"non_field_errors": "You can only edit your own medical records"}
                )

        return attrs


class MedicalRecordFilterSerializer(serializers.Serializer):
    """Serializer for filtering medical records"""

    patient_id = serializers.UUIDField(required=False)
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
    """Serializer for exporting medical records"""

    format = serializers.ChoiceField(choices=["pdf", "csv", "json"], default="pdf")
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    include_prescriptions = serializers.BooleanField(default=True)
    include_notes = serializers.BooleanField(default=True)
    password = serializers.CharField(
        required=False,
        style={"input_type": "password"},
        help_text="Password for encrypted PDF export",
    )


class MedicalRecordAuditSerializer(serializers.Serializer):
    """Serializer for audit log queries"""

    patient_id = serializers.UUIDField(required=False)
    specialist_id = serializers.IntegerField(required=False)
    action = serializers.ChoiceField(
        choices=["view", "create", "update", "export"], required=False
    )
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
