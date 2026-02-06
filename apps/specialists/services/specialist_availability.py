from datetime import date, timedelta
from typing import Dict
from django.utils import timezone

from ..models import Specialist, Availability
from apps.appointments.models import Appointment
from apps.core.exceptions.base_exceptions import NotFoundError


class SpecialistAvailabilityUseCases:
    """Handle specialist availability and slot calculations"""

    @staticmethod
    def calculate_availability_percentage(specialist_id: int) -> float:
        """Calculate specialist availability percentage"""
        # Get total available hours per week
        availabilities = Availability.objects.filter(
            specialist_id=specialist_id,
            is_recurring=True,
            valid_until__gte=timezone.now().date(),
        )

        if not availabilities.exists():
            return 0.0

        total_hours = 0
        for avail in availabilities:
            # Calculate hours per slot
            hours = (avail.end_time.hour - avail.start_time.hour) + (
                avail.end_time.minute - avail.start_time.minute
            ) / 60
            total_hours += hours

        # Maximum possible hours (8 hours/day * 5 days)
        max_hours = 40

        # Calculate percentage
        percentage = min((total_hours / max_hours) * 100, 100)

        return round(percentage, 2)

    @staticmethod
    def get_specialist_availability_slots(
        specialist: Specialist, date: date, duration_minutes: int = 90
    ) -> Dict:
        """Get available time slots for a specialist on a specific date"""

        if not specialist:
            raise NotFoundError(detail="Specialist not found")

        # Get specialist's availability for the day of week
        target_date = date
        day_of_week = target_date.weekday()  # Monday=0, Sunday=6

        availabilities = Availability.objects.filter(
            specialist=specialist,
            day_of_week=day_of_week,
            is_recurring=True,
            valid_from__lte=target_date,
            valid_until__gte=target_date,
        )

        # Get existing appointments for the day
        appointments = Appointment.objects.filter(
            specialist=specialist,
            appointment_date__date=target_date,
            status__in=["scheduled", "confirmed"],
        )

        available_slots = []
        for availability in availabilities:
            current_time = availability.start_time
            end_time = availability.end_time

            while current_time < end_time:
                # Calculate slot end time by adding duration to current time
                slot_end_datetime = timezone.datetime.combine(
                    target_date, current_time
                ) + timedelta(minutes=duration_minutes)
                slot_end = slot_end_datetime.time()

                # Check if slot would exceed availability end time
                if slot_end > end_time:
                    break

                slot_start_datetime = timezone.datetime.combine(
                    target_date, current_time
                )

                # Check if slot is available (no overlapping appointment)
                slot_available = True
                for appointment in appointments:
                    if (
                        slot_start_datetime < appointment.end_time
                        and slot_end_datetime > appointment.start_time
                    ):
                        slot_available = False
                        break

                if slot_available:
                    available_slots.append(
                        {
                            "start_time": current_time.strftime("%H:%M"),
                            "end_time": slot_end.strftime("%H:%M"),
                            "duration_minutes": duration_minutes,
                        }
                    )
                # Move to next slot
                current_time = slot_end

        return {
            "specialist_id": specialist.id,
            "date": date,
            "day_of_week": dict(Availability.DAY_CHOICES)[day_of_week],
            "available_slots": available_slots,
            "total_slots": len(available_slots),
        }
