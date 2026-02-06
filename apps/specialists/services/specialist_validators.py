from decimal import Decimal, InvalidOperation
from typing import Optional
from django.contrib.auth import get_user_model

from ..models import Specialist
from apps.core.exceptions.base_exceptions import (
    BusinessRuleError,
    ValidationError,
    NotFoundError,
)


class SpecialistValidator:
    """Validation logic for specialists"""

    MIN_YEARS_EXPERIENCE = 0
    MAX_YEARS_EXPERIENCE = 60
    MIN_CONSULTATION_FEE = Decimal("10.00")
    MAX_CONSULTATION_FEE = Decimal("1000.00")
    MIN_RATING = Decimal("0.00")
    MAX_RATING = Decimal("5.00")

    @staticmethod
    def validate_license_number(
        license_number: str, exclude_specialist_id: Optional[int] = None
    ):
        """Validate license number format and uniqueness"""
        if not license_number or not isinstance(license_number, str):
            raise ValidationError(detail="License number must be a non-empty string")

        if (
            not license_number
            or len(license_number.strip()) < 3
            or len(license_number.strip()) > 30
        ):
            raise ValidationError(
                detail="License number must be between 3 and 30 characters long"
            )

        # Check uniqueness
        query = Specialist.objects.filter(license_number=license_number)
        if exclude_specialist_id:
            query = query.exclude(id=exclude_specialist_id)

        if query.exists():
            raise ValidationError(detail="License number already registered")

        return license_number.strip()

    @staticmethod
    def validate_years_experience(years: int):
        """Validate years of experience"""
        if not isinstance(years, int):
            raise ValidationError(detail="Years of experience must be an integer")

        if years < SpecialistValidator.MIN_YEARS_EXPERIENCE:
            raise ValidationError(
                detail=f"Years experience cannot be less than {SpecialistValidator.MIN_YEARS_EXPERIENCE}"
            )

        if years > SpecialistValidator.MAX_YEARS_EXPERIENCE:
            raise ValidationError(
                detail=f"Years experience cannot exceed {SpecialistValidator.MAX_YEARS_EXPERIENCE}"
            )

        return years

    @staticmethod
    def validate_consultation_fee(fee: Decimal):
        """Validate consultation fee"""
        if not isinstance(fee, Decimal):
            raise ValidationError(detail="Consultation fee must be a decimal number")

        if fee < SpecialistValidator.MIN_CONSULTATION_FEE:
            raise ValidationError(
                detail=f"Consultation fee cannot be less than ${SpecialistValidator.MIN_CONSULTATION_FEE}"
            )

        if fee > SpecialistValidator.MAX_CONSULTATION_FEE:
            raise ValidationError(
                detail=f"Consultation fee cannot exceed ${SpecialistValidator.MAX_CONSULTATION_FEE}"
            )

        return fee

    @staticmethod
    def validate_rating(rating: int):
        """Validate specialist rating"""
        if not isinstance(rating, (int, float, Decimal)):
            raise ValidationError(detail="Rating must be a number")

        if rating < SpecialistValidator.MIN_RATING:
            raise ValidationError(
                detail=f"Rating cannot be less than {SpecialistValidator.MIN_RATING}"
            )

        if rating > SpecialistValidator.MAX_RATING:
            raise ValidationError(
                detail=f"Rating cannot exceed {SpecialistValidator.MAX_RATING}"
            )

        return rating

    @staticmethod
    def validate_specialist_creation(user_data, specialist_data):
        """Validate specialist creation data"""
        # Validate user exists and is not already a specialist
        User = get_user_model()

        user_id = user_data.get("user_id")
        try:
            user = User.objects.get(id=user_id)
            if hasattr(user, "specialist_profile"):
                raise ValidationError(detail="User already has a specialist profile")
        except User.DoesNotExist:
            raise NotFoundError(detail="User not found")

        # Validate specialist data
        license_number = specialist_data.get("license_number")
        SpecialistValidator.validate_license_number(license_number)

        years_experience = specialist_data.get("years_experience", 0)
        SpecialistValidator.validate_years_experience(years_experience)

        consultation_fee = specialist_data.get("consultation_fee", Decimal("0.00"))
        SpecialistValidator.validate_consultation_fee(consultation_fee)

        rating = specialist_data.get("rating", Decimal("0.00"))
        SpecialistValidator.validate_rating(rating)

        return user, specialist_data

    @staticmethod
    def can_handle_appointment_type(specialist, appointment_type):
        """Check if specialist can handle specific appointment type"""
        # Base implementation - all specialists can handle all types
        # This can be extended with more complex logic

        # Example: Some specialists might not handle emergency appointments
        if appointment_type == "emergency":
            # Check if specialist is trained for emergencies
            # This would check qualifications, training, etc.
            return "emergency_trained" in specialist.qualifications.lower()

        return True

    @staticmethod
    def validate_price_override(price_override, base_price):
        """Validate price override for services"""
        # Convert to Decimal if it's a string
        if isinstance(price_override, str):
            try:
                price_override = Decimal(price_override)
            except (ValueError, InvalidOperation):
                raise ValidationError(detail="Invalid price override format")

        if price_override < 0:
            raise ValidationError(detail="Price override cannot be negative")

        if price_override < base_price * Decimal("0.5"):
            raise BusinessRuleError(
                detail="Price override cannot be less than 50% of the base price"
            )

        # Price override should be reasonable (not more than 3x base price)
        if price_override > base_price * 3:
            raise BusinessRuleError(
                detail="Price override cannot exceed 3 times the base price"
            )

        return price_override
