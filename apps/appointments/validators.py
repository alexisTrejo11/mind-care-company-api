"""
Custom validators for appointment-related data
"""

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import datetime, timedelta
import re


def validate_appointment_date(date_time):
    """
    Validate appointment date and time constraints
    """
    now = timezone.now()

    # Cannot schedule in the past
    if date_time < now:
        raise ValidationError(_("Appointment cannot be scheduled in the past"))

    # Minimum 2 hours in advance (for new appointments)
    min_advance = now + timedelta(hours=2)
    if date_time < min_advance:
        raise ValidationError(
            _("Appointments must be scheduled at least 2 hours in advance")
        )

    # Maximum 3 months in advance
    max_advance = now + timedelta(days=90)
    if date_time > max_advance:
        raise ValidationError(
            _("Appointments cannot be scheduled more than 3 months in advance")
        )


def validate_appointment_duration(duration_minutes):
    """
    Validate appointment duration
    """
    if duration_minutes < 15:
        raise ValidationError(_("Appointment must be at least 15 minutes"))

    if duration_minutes > 240:  # 4 hours
        raise ValidationError(_("Appointment cannot exceed 4 hours"))

    # Validate it's in 15-minute increments
    if duration_minutes % 15 != 0:
        raise ValidationError(_("Appointment duration must be in 15-minute increments"))


def validate_meeting_link(link):
    """
    Validate video meeting link format
    """
    if not link:
        return

    # Common video meeting platforms
    patterns = [
        r"https?://meet\.google\.com/[\w-]+",
        r"https?://zoom\.us/j/[\w-]+",
        r"https?://teams\.microsoft\.com/l/meetup-join/[\w-]+",
        r"https?://meet\.jit\.si/[\w-]+",
        r"https?://whereby\.com/[\w-]+",
    ]

    if not any(re.match(pattern, link) for pattern in patterns):
        raise ValidationError(
            _("Invalid meeting link format. Please use a valid video meeting URL.")
        )


def validate_status_transition(current_status, new_status):
    """
    Validate allowed status transitions
    """
    allowed_transitions = {
        "scheduled": ["confirmed", "cancelled"],
        "confirmed": ["in_progress", "cancelled"],
        "in_progress": ["completed", "cancelled"],
        "completed": [],  # Final state
        "cancelled": [],  # Final state
        "no_show": [],  # Final state
    }

    if new_status not in allowed_transitions.get(current_status, []):
        raise ValidationError(
            _(f"Cannot change status from {current_status} to {new_status}")
        )


def validate_cancellation_time(appointment_datetime):
    """
    Validate appointment can be cancelled (minimum 1 hour before)
    """
    now = timezone.now()
    min_cancel_time = appointment_datetime - timedelta(hours=1)

    if now > min_cancel_time:
        raise ValidationError(
            _(
                "Appointments can only be cancelled up to 1 hour before the scheduled time"
            )
        )
