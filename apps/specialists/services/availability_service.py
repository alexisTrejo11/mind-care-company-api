import logging
from typing import Dict, Any, List
from django.contrib.auth import get_user_model

from core.exceptions.base_exceptions import (
    ValidationError,
    NotFoundError,
    ConflictError,
)

from ..models import Availability, Specialist

logger = logging.getLogger(__name__)
User = get_user_model()


class AvailabilityService:
    class AvailabilityService:
        """Servicio para gestión de disponibilidad"""

        @staticmethod
        def create_availability(
            specialist_id: int,
            day_of_week: int,
            start_time: str,
            end_time: str,
            is_recurring: bool = True,
            **kwargs,
        ) -> "Availability":
            """
            Crear bloque de disponibilidad
            """
            from ..models import Availability
            from ..validators import validate_availability_times

            try:
                specialist = Specialist.objects.get(id=specialist_id)

                validate_availability_times(start_time, end_time)

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
        specialist_id: int, date: str, service_duration: int
    ) -> List[Dict[str, Any]]:
        """
        Get available time slots for a specialist on a given date
        considering existing appointments.
        """
        from datetime import datetime, timedelta
        from apps.appointments.models import Appointment

        try:
            specialist = Specialist.objects.get(id=specialist_id)
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
            day_of_week = target_date.weekday()  # Monday=0, Sunday=6

            # Django (Sunday=0)
            django_day_of_week = (day_of_week + 1) % 7

            availabilities = specialist.availability.filter(
                day_of_week=django_day_of_week,
                valid_from__lte=target_date,
                valid_until__gte=target_date,
            )

            # Get existing appointments
            appointments = Appointment.objects.filter(
                specialist=specialist,
                appointment_date=target_date,
                status__in=["scheduled", "confirmed"],
            )

            slots = []

            for availability in availabilities:
                current_time = datetime.combine(target_date, availability.start_time)
                end_time = datetime.combine(target_date, availability.end_time)

                while current_time + timedelta(minutes=service_duration) <= end_time:
                    # Check for conflicts with existing appointments
                    slot_end = current_time + timedelta(minutes=service_duration)

                    conflict = any(
                        appointment.start_time
                        <= current_time.time()
                        < appointment.end_time
                        or appointment.start_time
                        < slot_end.time()
                        <= appointment.end_time
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
