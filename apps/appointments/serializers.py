from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta

from .models import Appointment
from .validators import (
    validate_appointment_date,
    validate_appointment_duration,
    validate_meeting_link,
    validate_status_transition,
    validate_cancellation_time,
)
from core.responses.api_response import APIResponse

User = get_user_model()


class AppointmentSerializer(serializers.ModelSerializer):
    """Base serializer for appointment operations"""

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

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    appointment_type_display = serializers.CharField(
        source="get_appointment_type_display", read_only=True
    )

    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient_id",
            "patient_name",
            "patient_email",
            "specialist_id",
            "specialist_name",
            "specialist_specialization",
            "appointment_type",
            "appointment_type_display",
            "appointment_date",
            "start_time",
            "end_time",
            "duration_minutes",
            "status",
            "status_display",
            "notes",
            "symptoms",
            "meeting_link",
            "room_number",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "status_display",
            "appointment_type_display",
            "patient_id",
            "patient_name",
            "patient_email",
            "specialist_id",
            "specialist_name",
            "specialist_specialization",
        ]

    def validate_appointment_date(self, value):
        """Validate appointment date constraints"""
        validate_appointment_date(value)

        # Check if it's a weekday (Monday=0, Sunday=6)
        if value.weekday() >= 5:  # Saturday or Sunday
            raise serializers.ValidationError(
                "Appointments are only available on weekdays (Monday-Friday)"
            )

        # Check business hours (8 AM - 8 PM)
        if value.hour < 8 or value.hour >= 20:
            raise serializers.ValidationError(
                "Appointments are only available between 8:00 AM and 8:00 PM"
            )

        return value

    def validate_duration_minutes(self, value):
        validate_appointment_duration(value)
        return value

    def validate_meeting_link(self, value):
        validate_meeting_link(value)
        return value

    def validate(self, attrs):
        """Cross-field validation"""
        # Ensure end_time is after start_time
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        duration_minutes = attrs.get("duration_minutes")

        if start_time and end_time:
            if end_time <= start_time:
                raise serializers.ValidationError(
                    {"end_time": "End time must be after start time"}
                )

            # Calculate duration from start and end times
            calculated_duration = (end_time - start_time).seconds // 60

            if duration_minutes and calculated_duration != duration_minutes:
                raise serializers.ValidationError(
                    {
                        "duration_minutes": f"Duration must match time difference ({calculated_duration} minutes)"
                    }
                )

        return attrs


class AppointmentCreateSerializer(AppointmentSerializer):
    """Serializer for creating new appointments"""

    patient_id = serializers.UUIDField(write_only=True, required=False)
    specialist_id = serializers.IntegerField(write_only=True, required=True)
    appointment_date = serializers.DateTimeField(required=True)
    duration_minutes = serializers.IntegerField(required=True)

    class Meta(AppointmentSerializer.Meta):
        fields = AppointmentSerializer.Meta.fields + ["patient_id", "specialist_id"]
        read_only_fields = [
            f
            for f in AppointmentSerializer.Meta.read_only_fields
            if f
            not in [
                "patient_id",
                "patient_name",
                "patient_email",
                "specialist_id",
                "specialist_name",
                "specialist_specialization",
            ]
        ]

    def validate_patient_id(self, value):
        """Validate patient exists and is active"""
        try:

            patient = User.objects.get(user_id=value, is_active=True)
            if patient.user_type != "patient":
                raise serializers.ValidationError("User is not a patient")
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Patient not found or inactive")

    def validate_specialist_id(self, value):
        """Validate specialist exists and accepts new patients"""
        from apps.specialists.models import Specialist

        try:
            specialist = Specialist.objects.get(id=value)

            if not specialist.is_accepting_new_patients:
                raise serializers.ValidationError(
                    "Specialist is not accepting new patients"
                )

            return value
        except Specialist.DoesNotExist:
            raise serializers.ValidationError("Specialist not found")

    def validate(self, attrs):
        """Additional validation for appointment creation"""
        attrs = super().validate(attrs)

        # For patients, they can only schedule for themselves
        request = self.context.get("request")
        if request and request.user.user_type == "patient":
            if "patient_id" in attrs and str(attrs["patient_id"]) != str(
                request.user.user_id
            ):
                raise serializers.ValidationError(
                    {
                        "patient_id": "Patients can only schedule appointments for themselves"
                    }
                )

        # Set default patient for patients
        if request and request.user.user_type == "patient":
            attrs["patient_id"] = request.user.user_id

        return attrs


class AppointmentUpdateSerializer(AppointmentSerializer):
    """Serializer for updating appointments (limited fields)"""

    class Meta(AppointmentSerializer.Meta):
        read_only_fields = AppointmentSerializer.Meta.read_only_fields + [
            "patient_id",
            "specialist_id",
            "appointment_type",
            "appointment_date",
            "start_time",
            "end_time",
            "duration_minutes",
        ]

    def validate_status(self, value):
        """Validate status transitions"""
        instance = getattr(self, "instance", None)
        if instance and value != instance.status:
            validate_status_transition(instance.status, value)

        return value

    def validate(self, attrs):
        """Validate update constraints"""
        instance = getattr(self, "instance", None)
        if not instance:
            return attrs

        # Check if appointment can be modified
        if instance.status in ["completed", "cancelled", "no_show"]:
            raise serializers.ValidationError(
                f"Cannot modify appointment with status: {instance.status}"
            )

        # Check if within modification window
        if "status" in attrs and attrs["status"] == "cancelled":
            validate_cancellation_time(instance.appointment_date)

        return attrs


class AppointmentRescheduleSerializer(serializers.Serializer):
    """Serializer for rescheduling appointments"""

    new_appointment_date = serializers.DateTimeField(required=True)
    new_duration_minutes = serializers.IntegerField(
        required=False, min_value=15, max_value=240
    )
    reason = serializers.CharField(required=False, max_length=500)

    def validate_new_appointment_date(self, value):
        validate_appointment_date(value)
        return value

    def validate(self, attrs):
        """Validate rescheduling constraints"""
        request = self.context.get("request")
        appointment = self.context.get("appointment")

        # Can only reschedule up to 24 hours before
        min_reschedule_time = appointment.appointment_date - timedelta(hours=24)

        if timezone.now() > min_reschedule_time:
            raise serializers.ValidationError(
                {
                    "new_appointment_date": "Appointments can only be rescheduled up to 24 hours before"
                }
            )

        # Maximum 2 reschedules per appointment
        # You might want to track this in the model or separate table

        return attrs


class AppointmentFilterSerializer(serializers.Serializer):
    """Serializer for filtering appointments"""

    status = serializers.ChoiceField(choices=Appointment.STATUS_CHOICES, required=False)
    appointment_type = serializers.ChoiceField(
        choices=Appointment.APPOINTMENT_TYPE_CHOICES, required=False
    )
    specialist_id = serializers.IntegerField(required=False)
    patient_id = serializers.UUIDField(required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    is_upcoming = serializers.BooleanField(required=False)
    is_past = serializers.BooleanField(required=False)
    search = serializers.CharField(required=False, max_length=100)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)
    ordering = serializers.ChoiceField(
        choices=["appointment_date", "-appointment_date", "created_at", "-created_at"],
        required=False,
        default="-appointment_date",
    )


class AppointmentStatsSerializer(serializers.Serializer):
    """Serializer for appointment statistics"""

    period = serializers.ChoiceField(
        choices=["today", "week", "month", "quarter", "year"], default="month"
    )
    specialist_id = serializers.IntegerField(required=False)
