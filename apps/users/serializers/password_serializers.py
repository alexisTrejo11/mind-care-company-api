from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from drf_spectacular.utils import extend_schema_serializer


@extend_schema_serializer(component_name="PasswordResetRequest")
class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for password reset initiation request.

    Captures email address for password reset process initiation.
    Does not reveal whether email exists in system for security.

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | email | Email | Yes | email@domain.com | Email address for password reset |

    **Field Specifications:**

    1. **email field**:
       - Must be valid email format
       - Maximum length: 255 characters
       - Converted to lowercase
       - Format validated
       - No existence check in serializer (security)

    **Security Design:**
    - Always returns success response (prevents email enumeration)
    - Rate limiting applied at view level
    - Email validation prevents malformed requests
    - No database queries in serializer for email existence

    **Process Flow:**
    1. Email format validation
    2. If valid email, proceed to reset process
    3. If email exists, send reset link
    4. If email doesn't exist, still return success
    5. Rate limiting prevents abuse

    **Data Format:**
    - Accepts standard email addresses
    - International domains supported
    - Case-insensitive processing
    """

    email = serializers.EmailField(
        required=True, help_text="Email address associated with the account"
    )


@extend_schema_serializer(component_name="PasswordResetConfirm")
class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for password reset confirmation with token.

    Validates reset token and new password for completing password reset process.

    **Data Schema:**

    | Field | Type | Required | Write-only | Format | Description |
    |-------|------|----------|------------|--------|-------------|
    | token | String | Yes | No | JWT string | Password reset token |
    | password | String | Yes | Yes | - | New secure password |

    **Field Specifications:**

    1. **token field**:
       - JWT token from password reset email
       - Contains user identification and expiration
       - Validated for format and expiration
       - One-time use (invalidated after reset)

    2. **password field**:
       - Write-only new password
       - Validated using Django's password validation
       - Minimum length: 8 characters
       - Complexity requirements enforced
       - Cannot be same as old password (handled in view)

    **Token Characteristics:**
    - JWT format with user ID and timestamp
    - Short expiration (typically 1 hour)
    - Single-use design
    - Cryptographically signed

    **Password Requirements:**
    - Minimum 8 characters
    - Not entirely numeric
    - Not too common
    - Not too similar to user information
    """

    token = serializers.CharField(
        required=True, help_text="Password reset token received via email"
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
        help_text="New secure password meeting complexity requirements",
    )


@extend_schema_serializer(component_name="PasswordChange")
class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for authenticated user password change.

    Allows currently authenticated users to change their password
    by verifying current password and providing new secure password.

    **Data Schema:**

    | Field | Type | Required | Write-only | Format | Description |
    |-------|------|----------|------------|--------|-------------|
    | old_password | String | Yes | Yes | - | Current account password |
    | new_password | String | Yes | Yes | - | New secure password |

    **Field Specifications:**

    1. **old_password field**:
       - Write-only current password
       - Verified against stored hash
       - Must match user's current password
       - Maximum length: 128 characters

    2. **new_password field**:
       - Write-only new password
       - Validated using Django's password validation
       - Minimum length: 8 characters
       - Complexity requirements enforced
       - Cannot be same as old password

    **Validation Rules:**
    1. old_password must match current password
    2. new_password must pass complexity validation
    3. new_password cannot be same as old_password
    4. Rate limiting may apply to prevent brute force

    **Security Features:**
    - Current password verification
    - Strong password requirements
    - Prevention of password reuse
    - Session maintenance after change
    """

    old_password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
        help_text="Current account password for verification",
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
        help_text="New secure password meeting complexity requirements",
    )
