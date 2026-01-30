import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime


from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from django.core.exceptions import ValidationError as DjangoValidationError

from core.exceptions.base_exceptions import (
    ValidationError,
    NotFoundError,
    ConflictError,
    BusinessRuleError,
)

from ..models import Appointment
from apps.specialists.models import Specialist
from apps.users.models import User


class AvailabilityChecker:
    """Service for checking appointment availability"""

    @staticmethod
    def check_specialist_availability(
        specialist_id: int,
        start_time: datetime,
        end_time: datetime,
        exclude_appointment_id: Optional[int] = None,
    ) -> bool:
        """
        Check if specialist is available for a time slot
        """
        from apps.specialists.models import Availability as SpecialistAvailability

        try:
            specialist = Specialist.objects.get(id=specialist_id)

            # Check specialist's general availability
            day_of_week = start_time.weekday()
            django_day_of_week = (day_of_week + 1) % 7  # Convert to Django format

            # Check if within working hours for that day
            availability = specialist.availability.filter(
                day_of_week=django_day_of_week,
                valid_from__lte=start_time.date(),
                valid_until__gte=end_time.date() if end_time else start_time.date(),
                start_time__lte=start_time.time(),
                end_time__gte=end_time.time() if end_time else start_time.time(),
            ).exists()

            if not availability:
                return False

            # Check for existing appointments
            appointments_query = Appointment.objects.filter(
                specialist=specialist,
                start_time__lt=end_time,
                end_time__gt=start_time,
                status__in=["scheduled", "confirmed", "in_progress"],
            )

            if exclude_appointment_id:
                appointments_query = appointments_query.exclude(
                    id=exclude_appointment_id
                )

            has_conflict = appointments_query.exists()

            return not has_conflict

        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")

    @staticmethod
    def get_available_time_slots(
        specialist_id: int,
        date: datetime.date,
        service_duration: int,
        lookahead_days: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Get all available time slots for a specialist on a given date
        """
        from apps.specialists.models import Availability as SpecialistAvailability

        try:
            specialist = Specialist.objects.get(id=specialist_id)
            day_of_week = date.weekday()
            django_day_of_week = (day_of_week + 1) % 7

            # Get specialist's availability for that day
            availabilities = specialist.availability.filter(
                day_of_week=django_day_of_week,
                valid_from__lte=date,
                valid_until__gte=date,
            ).order_by("start_time")

            if not availabilities:
                return []

            # Get existing appointments for that day
            existing_appointments = Appointment.objects.filter(
                specialist=specialist,
                appointment_date=date,
                status__in=["scheduled", "confirmed", "in_progress"],
            ).order_by("start_time")

            available_slots = []

            for availability in availabilities:
                current_time = datetime.combine(date, availability.start_time)
                end_time = datetime.combine(date, availability.end_time)

                while current_time + timedelta(minutes=service_duration) <= end_time:
                    slot_end = current_time + timedelta(minutes=service_duration)

                    # Check if slot conflicts with existing appointments
                    conflict = any(
                        app.start_time <= current_time < app.end_time
                        or app.start_time < slot_end <= app.end_time
                        for app in existing_appointments
                    )

                    if not conflict:
                        available_slots.append(
                            {
                                "start_time": current_time,
                                "end_time": slot_end,
                                "duration_minutes": service_duration,
                                "is_available": True,
                            }
                        )

                    # Move to next slot (15-minute increments)
                    current_time += timedelta(minutes=15)

            return available_slots

        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")
