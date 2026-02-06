import logging
from typing import Dict, Any, List
from django.contrib.auth import get_user_model
from datetime import date, time, datetime, timedelta
from django.utils import timezone
from apps.core.exceptions.base_exceptions import (
    ValidationError,
    NotFoundError,
    ConflictError,
)

from ..models import Availability, Specialist

logger = logging.getLogger(__name__)
User = get_user_model()


class AvailabilityUseCases:
    """Servicio para gestión de disponibilidad"""

    @staticmethod
    def validate_availability_times(start_time: time, end_time: time):
        """
        Validate availability time range.

        Args:
            start_time: Start time as time object or string
            end_time: End time as time object or string

        Raises:
            ValidationError: If times are invalid or start >= end
        """
        # Parse times to handle both string and time objects
        if not isinstance(start_time, time) and not isinstance(end_time, time):
            raise ValidationError(
                detail="start_time and end_time must be time objects",
                code="invalid_time_format",
            )

        if start_time >= end_time:
            raise ValidationError(
                detail="start_time must be before end_time",
                code="invalid_time_range",
            )

    @staticmethod
    def create_availability(
        specialist_id: int,
        day_of_week: int,
        start_time: time,
        end_time: time,
        valid_from: date,
        is_recurring: bool = True,
        **kwargs,
    ) -> "Availability":
        """
        Crear bloque de disponibilidad.

        Args:
            specialist_id: ID of specialist
            day_of_week: Day of week (1-7, where 1=Monday)
            start_time: Start time as time object or HH:MM string
            end_time: End time as time object or HH:MM string
            is_recurring: Whether this is a recurring availability
            **kwargs: Additional fields like valid_from, valid_until

        Returns:
            Availability object

        Raises:
            NotFoundError: If specialist doesn't exist
            ValidationError: If time validation fails
            ConflictError: If availability overlaps with existing schedule
        """
        from ..models import Availability

        if not isinstance(day_of_week, int) or day_of_week < 1 or day_of_week > 7:
            raise ValidationError(
                detail="day_of_week must be an integer between 1 (Monday) and 7 (Sunday)",
                code="invalid_day_of_week",
            )
        if not isinstance(start_time, time):
            raise ValidationError(
                detail="start_time must be a time object",
                code="invalid_time_format",
            )
        if not isinstance(end_time, time):
            raise ValidationError(
                detail="end_time must be a time object",
                code="invalid_time_format",
            )
        try:
            specialist = Specialist.objects.get(id=specialist_id)
            AvailabilityUseCases.validate_availability_times(start_time, end_time)

            overlapping = Availability.objects.filter(
                specialist=specialist,
                day_of_week=day_of_week,
                start_time__lt=end_time,
                end_time__gt=start_time,
            )

            if overlapping.exists():
                raise ConflictError(
                    detail="Availability overlaps with existing schedule",
                    code="availability_overlap",
                )

            availability = Availability.objects.create(
                specialist=specialist,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
                is_recurring=is_recurring,
                valid_from=valid_from,
                **kwargs,
            )

            logger.info(
                f"Availability created for specialist {specialist_id}: "
                f"{day_of_week} {start_time}-{end_time}"
            )

            return availability

        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")

    @staticmethod
    def get_available_slots(
        specialist_id: int, target_date: date, service_duration: int
    ) -> List[Dict[str, Any]]:
        """
        Get available time slots for a specialist on a given date
        considering existing appointments.
        """
        from apps.appointments.models import Appointment

        if not isinstance(target_date, date):
            raise ValidationError(detail="date must be a date object")
        if not isinstance(service_duration, int) or service_duration <= 0:
            raise ValidationError(detail="service_duration must be a positive integer")

        try:
            specialist = Specialist.objects.get(id=specialist_id)
            day_of_week = target_date.weekday()  # Monday=0, Sunday=6

            # Django (Sunday=0)
            django_day_of_week = (day_of_week + 1) % 7

            availabilities = specialist.availability.filter(
                day_of_week=django_day_of_week,
                valid_from__lte=target_date,
                valid_until__gte=target_date,
            )

            # Get existing appointments
            # Note: appointment_date is DateTimeField, so we need to filter by date part
            appointments = Appointment.objects.filter(
                specialist=specialist,
                appointment_date__date=target_date,
                status__in=["scheduled", "confirmed"],
            )

            slots = []

            for availability in availabilities:
                current_time = timezone.make_aware(
                    datetime.combine(target_date, availability.start_time)
                )
                end_time = timezone.make_aware(
                    datetime.combine(target_date, availability.end_time)
                )

                while current_time + timedelta(minutes=service_duration) <= end_time:
                    # Check for conflicts with existing appointments
                    slot_end = current_time + timedelta(minutes=service_duration)

                    conflict = any(
                        appointment.start_time <= current_time < appointment.end_time
                        or appointment.start_time < slot_end <= appointment.end_time
                        for appointment in appointments
                    )

                    if not conflict:
                        slots.append(
                            {
                                "start_time": current_time.time(),
                                "end_time": slot_end.time(),
                                "date": target_date,
                            }
                        )

                    # Increment in 30-minute blocks
                    current_time += timedelta(minutes=30)

            return slots

        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")
        except ValueError:
            raise ValidationError(detail="Invalid date format. Use YYYY-MM-DD")
