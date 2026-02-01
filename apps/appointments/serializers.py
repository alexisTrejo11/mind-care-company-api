from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Appointment
from specialists.models import Specialist
from core.exceptions.base_exceptions import (
    ValidationError,
    NotFoundError,
)

User = get_user_model()


class AppointmentSerializer(serializers.ModelSerializer):
    """Serializer for reading appointment data"""

    patient_name = serializers.SerializerMethodField()
    specialist_name = serializers.SerializerMethodField()
    specialist_specialty = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient",
            "patient_name",
            "specialist",
            "specialist_name",
            "specialist_specialty",
            "appointment_type",
            "appointment_date",
            "start_time",
            "end_time",
            "duration_minutes",
            "status",
            "notes",
            "symptoms",
            "meeting_link",
            "room_number",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_patient_name(self, obj):
        return obj.patient.get_full_name() if obj.patient else None

    def get_specialist_name(self, obj):
        if obj.specialist and obj.specialist.user:
            return obj.specialist.user.get_full_name()
        return None

    def get_specialist_specialty(self, obj):
        return obj.specialist.specialty if obj.specialist else None


class AppointmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new appointments"""

    patient_id = serializers.IntegerField(required=False)
    specialist_id = serializers.IntegerField()

    class Meta:
        model = Appointment
        fields = [
            "specialist_id",
            "patient_id",
            "appointment_type",
            "appointment_date",
            "start_time",
            "end_time",
            "duration_minutes",
            "notes",
            "symptoms",
            "meeting_link",
            "room_number",
        ]

    def validate(self, data):
        # Get request user
        request = self.context.get("request")
        user = request.user if request else None

        # Set patient to current user if not provided (for patients booking)
        if "patient_id" not in data or data["patient_id"] is None:
            if user and user.user_type == "patient":
                data["patient"] = user
            else:
                raise ValidationError(
                    detail="Patient ID is required or user must be a patient"
                )
        else:
            # Validate patient exists and is a patient type
            patient_id = data.pop("patient_id")
            try:
                patient = User.objects.get(id=patient_id, user_type="patient")
                data["patient"] = patient
            except User.DoesNotExist:
                raise NotFoundError(detail="Patient not found")

            # Check if user has permission to create appointment for this patient
            if user and user.user_type == "patient" and user != patient:
                raise ValidationError(
                    detail="Patients can only create appointments for themselves"
                )

        # Validate specialist exists
        specialist_id = data.get("specialist_id")
        try:
            specialist = Specialist.objects.get(id=specialist_id)
            data["specialist"] = specialist
        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")

        # Validate appointment date/time logic
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        appointment_date = data.get("appointment_date")
        duration_minutes = data.get("duration_minutes")

        if start_time >= end_time:
            raise ValidationError(detail="Start time must be before end time")

        if appointment_date.date() != start_time.date():
            raise ValidationError(detail="Appointment date must match start time date")

        # Validate duration matches time difference
        expected_duration = (end_time - start_time).total_seconds() / 60
        if abs(duration_minutes - expected_duration) > 1:  # Allow 1 minute tolerance
            raise ValidationError(
                detail=f"Duration {duration_minutes} minutes doesn't match time slot"
            )

        # Validate duration is positive and reasonable
        if duration_minutes < 5:
            raise ValidationError(detail="Minimum appointment duration is 5 minutes")
        if duration_minutes > 480:  # 8 hours max
            raise ValidationError(detail="Maximum appointment duration is 480 minutes")

        return data


class AppointmentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating appointments (admin/staff only)"""

    class Meta:
        model = Appointment
        fields = [
            "status",
            "notes",
            "symptoms",
            "meeting_link",
            "room_number",
        ]

    def validate_status(self, value):
        request = self.context.get("request")
        appointment = self.context.get("appointment")

        if not request or not appointment:
            return value

        # Patients can only cancel their own appointments
        if request.user.user_type == "patient":
            if value != "cancelled" and appointment.status != "scheduled":
                raise ValidationError(detail="Patients can only cancel appointments")

        return value


class AppointmentRescheduleSerializer(serializers.Serializer):
    """Serializer for rescheduling appointments"""

    new_appointment_date = serializers.DateTimeField()
    new_start_time = serializers.DateTimeField()
    new_end_time = serializers.DateTimeField()
    new_duration_minutes = serializers.IntegerField(min_value=5)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate(self, data):
        request = self.context.get("request")
        appointment = self.context.get("appointment")

        if not appointment:
            raise ValidationError(detail="Appointment context required")

        new_start_time = data["new_start_time"]
        new_end_time = data["new_end_time"]
        new_appointment_date = data["new_appointment_date"]
        new_duration_minutes = data["new_duration_minutes"]

        # Validate new date/time logic
        if new_start_time >= new_end_time:
            raise ValidationError(detail="Start time must be before end time")

        if new_appointment_date.date() != new_start_time.date():
            raise ValidationError(detail="Appointment date must match start time date")

        # Validate new time is in the future
        if new_start_time <= timezone.now():
            raise ValidationError(detail="Cannot reschedule to past time")

        # Validate new duration matches time difference
        expected_duration = (new_end_time - new_start_time).total_seconds() / 60
        if abs(new_duration_minutes - expected_duration) > 1:
            raise ValidationError(
                detail=f"Duration {new_duration_minutes} minutes doesn't match time slot"
            )

        # Verify user has permission to reschedule
        if request:
            if (
                request.user.user_type == "patient"
                and appointment.patient != request.user
            ):
                raise ValidationError(
                    detail="Cannot reschedule another patient's appointment"
                )

        return data


class AppointmentStatsSerializer(serializers.Serializer):
    """Serializer for appointment statistics parameters"""

    period = serializers.ChoiceField(
        choices=["today", "week", "month", "year", "custom"], required=True
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    specialist_id = serializers.IntegerField(required=False)

    def validate(self, data):
        period = data.get("period")

        if period == "custom":
            if not data.get("start_date") or not data.get("end_date"):
                raise ValidationError(
                    detail="start_date and end_date are required for custom period"
                )
            if data["start_date"] > data["end_date"]:
                raise ValidationError(detail="start_date must be before end_date")

        return data
