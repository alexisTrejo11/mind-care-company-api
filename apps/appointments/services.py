from datetime import timedelta, time as datetime_time
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q, Avg, Sum
from .models import Appointment
from specialists.models import Specialist
from core.exceptions.base_exceptions import (
    BusinessRuleError,
    NotFoundError,
    ConflictError,
)


class AppointmentService:
    """Service layer for appointment business logic"""

    # Clinic operating hours (9 AM to 7 PM)
    CLINIC_OPEN_HOUR = 9
    CLINIC_CLOSE_HOUR = 19

    # Minimum advance booking (1 hour)
    MIN_ADVANCE_BOOKING_HOURS = 1

    # Maximum advance booking (90 days)
    MAX_ADVANCE_BOOKING_DAYS = 90

    @staticmethod
    def is_within_clinic_hours(appointment_time):
        """Check if appointment time is within clinic operating hours"""
        hour = appointment_time.hour
        return (
            hour >= AppointmentService.CLINIC_OPEN_HOUR
            and hour < AppointmentService.CLINIC_CLOSE_HOUR
        )

    @staticmethod
    def validate_booking_time(appointment_datetime):
        """Validate if booking time meets requirements"""
        now = timezone.now()

        # Check if in the future
        if appointment_datetime <= now:
            raise BusinessRuleError(
                detail="Appointment must be scheduled for a future time"
            )

        # Check minimum advance booking
        min_booking_time = now + timedelta(
            hours=AppointmentService.MIN_ADVANCE_BOOKING_HOURS
        )
        if appointment_datetime < min_booking_time:
            raise BusinessRuleError(
                detail=f"Appointments must be booked at least "
                f"{AppointmentService.MIN_ADVANCE_BOOKING_HOURS} hour(s) in advance"
            )

        # Check maximum advance booking
        max_booking_time = now + timedelta(
            days=AppointmentService.MAX_ADVANCE_BOOKING_DAYS
        )
        if appointment_datetime > max_booking_time:
            raise BusinessRuleError(
                detail=f"Appointments cannot be booked more than "
                f"{AppointmentService.MAX_ADVANCE_BOOKING_DAYS} days in advance"
            )

        # Check clinic hours
        if not AppointmentService.is_within_clinic_hours(appointment_datetime):
            raise BusinessRuleError(
                detail=f"Appointments must be scheduled between "
                f"{AppointmentService.CLINIC_OPEN_HOUR}:00 and "
                f"{AppointmentService.CLINIC_CLOSE_HOUR}:00"
            )

        # Check if it's a weekday (Monday=0, Sunday=6)
        if appointment_datetime.weekday() >= 5:  # Saturday or Sunday
            raise BusinessRuleError(
                detail="Appointments are only available on weekdays"
            )

    @staticmethod
    def check_specialist_availability(
        specialist, start_time, end_time, exclude_appointment_id=None
    ):
        """Check if specialist is available for the given time slot"""
        # Check if specialist is active
        if not specialist.is_active:
            raise BusinessRuleError(detail="Specialist is not active")

        # Build query for overlapping appointments
        overlap_query = Q(
            specialist=specialist,
            status__in=["scheduled", "confirmed", "in_progress"],
            start_time__lt=end_time,
            end_time__gt=start_time,
        )

        # Exclude current appointment for updates/reschedules
        if exclude_appointment_id:
            overlap_query &= ~Q(id=exclude_appointment_id)

        # Check for overlaps
        overlapping_appointments = Appointment.objects.filter(overlap_query)

        if overlapping_appointments.exists():
            raise ConflictError(
                detail="Specialist already has an appointment scheduled for this time",
                metadata={
                    "specialist_id": specialist.id,
                    "conflicting_appointments": list(
                        overlapping_appointments.values_list("id", flat=True)
                    ),
                },
            )

    @staticmethod
    def check_patient_availability(
        patient, start_time, end_time, exclude_appointment_id=None
    ):
        """Check if patient doesn't have overlapping appointments"""
        # Build query for overlapping appointments
        overlap_query = Q(
            patient=patient,
            status__in=["scheduled", "confirmed", "in_progress"],
            start_time__lt=end_time,
            end_time__gt=start_time,
        )

        # Exclude current appointment for updates/reschedules
        if exclude_appointment_id:
            overlap_query &= ~Q(id=exclude_appointment_id)

        # Check for overlaps
        overlapping_appointments = Appointment.objects.filter(overlap_query)

        if overlapping_appointments.exists():
            raise ConflictError(
                detail="Patient already has an appointment scheduled for this time",
                metadata={
                    "patient_id": patient.id,
                    "conflicting_appointments": list(
                        overlapping_appointments.values_list("id", flat=True)
                    ),
                },
            )

    @staticmethod
    def validate_appointment_time_slot(start_time, end_time):
        """Validate appointment time slot meets business rules"""
        duration = (end_time - start_time).total_seconds() / 60

        # Check minimum appointment duration
        if duration < 15:
            raise BusinessRuleError(detail="Minimum appointment duration is 15 minutes")

        # Check if appointment is in standard intervals (15, 30, 45, 60 minutes)
        if duration % 15 != 0:
            raise BusinessRuleError(
                detail="Appointment duration must be in 15-minute increments (15, 30, 45, 60, etc.)"
            )

        # Check maximum appointment duration
        if duration > 120:  # 2 hours max
            raise BusinessRuleError(
                detail="Maximum appointment duration is 120 minutes"
            )

    @classmethod
    @transaction.atomic
    def create_appointment(cls, **validated_data):
        """Create a new appointment with business logic validation"""

        # Extract data
        patient = validated_data.get("patient")
        specialist = validated_data.get("specialist")
        start_time = validated_data.get("start_time")
        end_time = validated_data.get("end_time")
        appointment_date = validated_data.get("appointment_date")

        # Validate booking time
        cls.validate_booking_time(start_time)

        # Validate time slot
        cls.validate_appointment_time_slot(start_time, end_time)

        # Check specialist availability
        cls.check_specialist_availability(specialist, start_time, end_time)

        # Check patient availability
        cls.check_patient_availability(patient, start_time, end_time)

        # Check if specialist can handle appointment type
        if not specialist.can_handle_appointment_type(
            validated_data.get("appointment_type")
        ):
            raise BusinessRuleError(
                detail=f"Specialist cannot handle {validated_data.get('appointment_type')} appointments"
            )

        # Check specialist's maximum daily appointments
        specialist_daily_count = Appointment.objects.filter(
            specialist=specialist,
            appointment_date=appointment_date.date(),
            status__in=["scheduled", "confirmed"],
        ).count()

        if specialist_daily_count >= specialist.max_daily_appointments:
            raise BusinessRuleError(
                detail="Specialist has reached maximum daily appointments"
            )

        # Create appointment
        appointment = Appointment.objects.create(**validated_data)

        # Log creation
        # AppointmentAuditService.log_creation(appointment, validated_by=request.user)

        return appointment

    @classmethod
    @transaction.atomic
    def cancel_appointment(cls, appointment: Appointment, cancelled_by, reason=None):
        """Cancel an appointment with business logic validation"""

        # Check if appointment can be cancelled
        if appointment.status in ["completed", "cancelled", "no_show"]:
            raise BusinessRuleError(
                detail=f"Cannot cancel appointment with status: {appointment.status}"
            )

        # Check cancellation policy (minimum 24 hours notice)
        cancellation_deadline = appointment.start_time - timedelta(hours=24)
        if timezone.now() > cancellation_deadline:
            if cancelled_by.user_type == "patient":
                raise BusinessRuleError(
                    detail="Appointments must be cancelled at least 24 hours in advance"
                )
            # Admin/staff can still cancel but mark as late cancellation
            appointment.notes = (
                f"{appointment.notes}\n\nLate cancellation by {cancelled_by}"
            )

        # Perform cancellation
        appointment.status = "cancelled"
        if reason:
            appointment.notes = f"{appointment.notes}\n\nCancellation reason: {reason}"
        appointment.save()

        # Log cancellation
        # AppointmentAuditService.log_cancellation(appointment, cancelled_by, reason)

        return appointment

    @classmethod
    @transaction.atomic
    def reschedule_appointment(cls, appointment: Appointment, **validated_data):
        """Reschedule an appointment with business logic validation"""
        # Check if appointment can be rescheduled
        if appointment.status in ["completed", "cancelled", "no_show", "in_progress"]:
            raise BusinessRuleError(
                detail=f"Cannot reschedule appointment with status: {appointment.status}"
            )

        new_start_time = validated_data["new_start_time"]
        new_end_time = validated_data["new_end_time"]
        new_appointment_date = validated_data["new_appointment_date"]
        new_duration_minutes = validated_data["new_duration_minutes"]

        # Validate new booking time
        cls.validate_booking_time(new_start_time)

        # Validate new time slot
        cls.validate_appointment_time_slot(new_start_time, new_end_time)

        # Check specialist availability (excluding current appointment)
        cls.check_specialist_availability(
            appointment.specialist,
            new_start_time,
            new_end_time,
            exclude_appointment_id=appointment.id,
        )

        # Check patient availability (excluding current appointment)
        cls.check_patient_availability(
            appointment.patient,
            new_start_time,
            new_end_time,
            exclude_appointment_id=appointment.id,
        )

        # Check if new time is at least 2 hours different
        time_difference = abs(
            (new_start_time - appointment.start_time).total_seconds() / 3600
        )
        if time_difference < 2:
            raise BusinessRuleError(
                detail="Rescheduled appointment must be at least 2 hours different from original time"
            )

        # Update appointment
        appointment.start_time = new_start_time
        appointment.end_time = new_end_time
        appointment.appointment_date = new_appointment_date
        appointment.duration_minutes = new_duration_minutes
        appointment.status = "scheduled"  # Reset to scheduled

        if validated_data.get("reason"):
            appointment.notes = (
                f"{appointment.notes}\n\nRescheduled reason: {validated_data['reason']}"
            )

        appointment.save()

        # Log reschedule
        # AppointmentAuditService.log_reschedule(appointment, **validated_data)

        return appointment

    @classmethod
    def get_appointment_statistics(cls, period="month", specialist_id=None):
        """Get appointment statistics for the given period"""
        now = timezone.now()

        # Define date range based on period
        if period == "today":
            start_date = now.date()
            end_date = now.date()
        elif period == "week":
            start_date = now.date() - timedelta(days=now.weekday())
            end_date = start_date + timedelta(days=6)
        elif period == "month":
            start_date = now.date().replace(day=1)
            # Get last day of month
            if start_date.month == 12:
                end_date = start_date.replace(
                    year=start_date.year + 1, month=1, day=1
                ) - timedelta(days=1)
            else:
                end_date = start_date.replace(
                    month=start_date.month + 1, day=1
                ) - timedelta(days=1)
        elif period == "year":
            start_date = now.date().replace(month=1, day=1)
            end_date = now.date().replace(month=12, day=31)
        else:
            # Custom period handled by serializer
            return {}

        # Build base query
        query = Appointment.objects.filter(
            appointment_date__date__range=[start_date, end_date]
        )

        # Filter by specialist if provided
        if specialist_id:
            query = query.filter(specialist_id=specialist_id)

        # Calculate statistics
        total_appointments = query.count()

        if total_appointments == 0:
            return {
                "period": period,
                "start_date": start_date,
                "end_date": end_date,
                "total_appointments": 0,
                "message": "No appointments found for the selected period",
            }

        status_counts = query.values("status").annotate(count=Count("id"))
        status_distribution = {item["status"]: item["count"] for item in status_counts}

        type_counts = query.values("appointment_type").annotate(count=Count("id"))
        type_distribution = {
            item["appointment_type"]: item["count"] for item in type_counts
        }

        # Calculate averages
        avg_duration = (
            query.aggregate(avg_duration=Avg("duration_minutes"))["avg_duration"] or 0
        )

        # Get busiest day
        busiest_day = (
            query.values("appointment_date__date")
            .annotate(count=Count("id"))
            .order_by("-count")
            .first()
        )

        # Get cancellation rate
        cancelled_count = query.filter(status="cancelled").count()
        cancellation_rate = (
            (cancelled_count / total_appointments) * 100
            if total_appointments > 0
            else 0
        )

        # Get no-show rate
        no_show_count = query.filter(status="no_show").count()
        no_show_rate = (
            (no_show_count / total_appointments) * 100 if total_appointments > 0 else 0
        )

        return {
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "total_appointments": total_appointments,
            "status_distribution": status_distribution,
            "type_distribution": type_distribution,
            "averages": {"duration_minutes": round(avg_duration, 1)},
            "busiest_day": busiest_day,
            "rates": {
                "cancellation_rate": round(cancellation_rate, 2),
                "no_show_rate": round(no_show_rate, 2),
                "completion_rate": round(100 - cancellation_rate - no_show_rate, 2),
            },
        }
