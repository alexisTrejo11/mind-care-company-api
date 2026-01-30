from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import datetime, timedelta
import re


def validate_license_number(value):
    """
    General validation for specialist license numbers.
    The format may vary by country, but this function checks for a basic pattern.
    Expected format: COUNTRYCODE-NUMBER
    """
    # Ejemplo: MEX123456, USA-12345, ESP78901
    pattern = r"^[A-Z]{2,4}[-]?\d{5,10}$"
    if not re.match(pattern, value):
        raise ValidationError(
            _("License number must follow format: COUNTRYCODE-NUMBER (e.g., MEX123456)")
        )


def validate_consultation_fee(value):
    """
    Validate that the consultation fee is within reasonable bounds
    """
    MINIMAL_AMOUNT = 0
    MAXIMAL_REASONABLE_AMOUNT = 100_000
    if value <= MINIMAL_AMOUNT:
        raise ValidationError(_("Consultation fee must be greater than 0"))

    if value > MAXIMAL_REASONABLE_AMOUNT:
        raise ValidationError(_("Consultation fee cannot exceed 10,000"))


def validate_service_duration_mins(value):
    """
    Validate that the service duration is within reasonable bounds
    """
    MIN_CONSULTATION_MINS = 15
    MAX_DURATION_MINS = 480  # 8 hours
    if value < MIN_CONSULTATION_MINS:
        raise ValidationError(_("Service duration must be at least 15 minutes"))

    if value > MAX_DURATION_MINS:
        raise ValidationError(_("Service duration cannot exceed 8 hours"))


def validate_availability_times(start_time, end_time):
    """
    Validate that availability times are logical
    """
    if end_time <= start_time:
        raise ValidationError(_("End time must be after start time"))

    # Minimum 1 hr, maximum 12 hours per slot
    duration = datetime.combine(timezone.now().date(), end_time) - datetime.combine(
        timezone.now().date(), start_time
    )

    if duration < timedelta(hours=1):
        raise ValidationError(_("Availability slot must be at least 1 hour"))

    if duration > timedelta(hours=12):
        raise ValidationError(_("Availability slot cannot exceed 12 hours"))


def validate_availability_dates(valid_from, valid_until):
    """
    Validate availability dates
    """
    if valid_from < timezone.now().date():
        raise ValidationError(_("Start date cannot be in the past"))

    if valid_until and valid_until <= valid_from:
        raise ValidationError(_("End date must be after start date"))

    # Maximum 1 year in advance
    max_future_date = timezone.now().date() + timedelta(days=365)
    if valid_from > max_future_date:
        raise ValidationError(_("Start date cannot be more than 1 year in the future"))


def validate_specialization_combo(specialization, service_category):
    """
    Validate that the specialist's specialization aligns with the service category
    """
    mapping = {
        "psychologist": ["mental_health", "therapy"],
        "psychiatrist": ["mental_health", "specialist_consultation"],
        "general_physician": ["general_medicine"],
        "nutritionist": ["wellness"],
        "physiotherapist": ["therapy"],
        "neurologist": ["specialist_consultation", "diagnostic"],
    }

    allowed_categories = mapping.get(specialization, [])
    if allowed_categories and service_category not in allowed_categories:
        raise ValidationError(
            _(
                f"{specialization.capitalize()} can only offer services in: "
                f'{", ".join(allowed_categories)}'
            )
        )
