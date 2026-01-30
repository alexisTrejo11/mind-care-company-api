from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.medical.models import MedicalRecord
from core.exceptions.base_exceptions import (
    AuthorizationError,
    PrivacyError,
)

User = get_user_model()


class PrivacyService:
    """Service for handling medical record privacy and HIPAA compliance"""

    @staticmethod
    def check_record_access(
        record: MedicalRecord, user: User, action: str = "view"
    ) -> None:
        """
        Check if user can access medical record based on HIPAA rules

        Args:
            record: MedicalRecord instance
            user: User making the request
            action: 'view', 'update', or 'delete'

        Raises:
            AuthorizationError if access is denied
            PrivacyError for privacy violations
        """
        if not user.is_authenticated:
            raise AuthorizationError(
                detail="Authentication required", code="authentication_required"
            )

        if not user.is_active:
            raise AuthorizationError(
                detail="Account is inactive", code="account_inactive"
            )

        # Define access rules based on confidentiality level
        access_rules = {
            "standard": {
                "patient": ["view"],
                "specialist": ["view", "update"],
                "staff": ["view"],
                "admin": ["view", "update", "delete"],
            },
            "sensitive": {
                "patient": ["view"],
                "specialist": ["view", "update"],
                "admin": ["view", "update", "delete"],
            },
            "highly_sensitive": {
                "patient": ["view"],
                "specialist": ["view", "update"],
                "admin": ["view", "update", "delete"],
            },
        }

        # Get allowed actions for this user type and confidentiality level
        allowed_actions = access_rules.get(record.confidentiality_level, {}).get(
            user.user_type, []
        )

        if action not in allowed_actions:
            raise PrivacyError(
                detail=f"Access denied for {action} action on {record.confidentiality_level} record",
                code=f"access_denied_{action}",
            )

        # Additional checks for specialists
        if user.user_type == "specialist":
            if not hasattr(user, "specialist_profile"):
                raise AuthorizationError(
                    detail="Specialist profile not found",
                    code="specialist_profile_missing",
                )

            # Specialists can only access records they created
            if user.specialist_profile != record.specialist:
                raise PrivacyError(
                    detail="Specialists can only access their own medical records",
                    code="non_owned_record_access",
                )
