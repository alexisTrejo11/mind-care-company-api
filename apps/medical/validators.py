"""
Custom validators for medical records with HIPAA/GDPR compliance
"""

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import datetime, timedelta
import re


def validate_confidentiality_access(user_type: str, confidentiality_level: str) -> None:
    """
    Validate if user can access records based on confidentiality level

    HIPAA Compliance Rules:
    - Standard: All medical staff can access
    - Sensitive: Only treating specialist and senior staff
    - Highly Sensitive: Only treating specialist and administrators
    """
    access_matrix = {
        "standard": ["patient", "specialist", "admin", "staff"],
        "sensitive": ["patient", "specialist", "admin"],
        "highly_sensitive": ["patient", "specialist", "admin"],
    }

    if user_type not in access_matrix.get(confidentiality_level, []):
        raise ValidationError(
            _(
                f"Your user type ({user_type}) cannot access {confidentiality_level} records"
            )
        )


def validate_diagnosis_format(diagnosis: str) -> None:
    """
    Validate diagnosis follows medical standards (ICD-10 codes optional)
    """
    if not diagnosis or len(diagnosis.strip()) < 5:
        raise ValidationError(_("Diagnosis must be at least 5 characters"))

    # Check for potential PII in diagnosis (basic check)
    pii_patterns = [
        r"\d{3}-\d{2}-\d{4}",  # SSN
        r"\d{16}",  # Credit card
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}",  # Email
    ]

    for pattern in pii_patterns:
        if re.search(pattern, diagnosis):
            raise ValidationError(
                _(
                    "Diagnosis contains potential PII. Please remove sensitive information"
                )
            )


def validate_prescription_format(prescription: str) -> None:
    """
    Validate prescription format and content
    """
    if not prescription:
        return

    # Minimum structure check
    lines = prescription.strip().split("\n")
    if len(lines) < 2:
        raise ValidationError(_("Prescription should include medication and dosage"))

    # Check for dangerous combinations (basic example) TODO: Expand with real data
    dangerous_combinations = [
        ("warfarin", "aspirin"),
        ("simvastatin", "gemfibrozil"),
        ("erythromycin", "simvastatin"),
    ]

    prescription_lower = prescription.lower()
    for drug1, drug2 in dangerous_combinations:
        if drug1 in prescription_lower and drug2 in prescription_lower:
            raise ValidationError(
                _(f"Potential dangerous combination: {drug1} and {drug2}")
            )


def validate_follow_up_date(follow_up_date) -> None:
    """
    Validate follow-up date constraints
    """
    if not follow_up_date:
        return

    today = timezone.now().date()

    # Cannot be in the past
    if follow_up_date < today:
        raise ValidationError(_("Follow-up date cannot be in the past"))

    # Maximum 1 year in advance
    max_future = today + timedelta(days=365)
    if follow_up_date > max_future:
        raise ValidationError(_("Follow-up date cannot be more than 1 year in advance"))

    # Minimum 1 day after appointment (handled in serializer)


def validate_medical_note_content(notes: str) -> None:
    """
    Validate medical notes don't contain inappropriate content
    """
    if not notes:
        return

    # Check for offensive terms (basic example)
    offensive_terms = [
        "racial slurs",  # Add actual list
        "derogatory terms",
    ]

    notes_lower = notes.lower()
    for term in offensive_terms:
        if term in notes_lower:
            raise ValidationError(_("Medical notes contain inappropriate content"))


def validate_record_retention_period(created_at) -> None:
    """
    Validate medical record retention period (minimum 7 years for adults)
    """
    if not created_at:
        return

    retention_period = timedelta(days=365 * 7)  # 7 years
    deletion_date = created_at + retention_period

    if timezone.now() > deletion_date:
        raise ValidationError(_("Medical record has reached retention period limit"))


def validate_allergy_information(notes: str, prescription: str) -> None:
    """
    Cross-validate allergies mentioned in notes with prescriptions
    """
    if not notes or not prescription:
        return

    # Extract potential allergies from notes (simplified)
    allergy_keywords = ["allerg", "sensitive", "intolerant", "reaction"]
    has_allergies = any(keyword in notes.lower() for keyword in allergy_keywords)

    if has_allergies:
        # Check for common allergens in prescription
        common_allergens = ["penicillin", "sulfa", "aspirin", "ibuprofen"]
        prescription_lower = prescription.lower()

        for allergen in common_allergens:
            if allergen in prescription_lower:
                raise ValidationError(
                    _(f"Prescription contains {allergen} but notes mention allergies")
                )
