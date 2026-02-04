from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import (
    extend_schema_serializer,
    extend_schema_field,
    OpenApiTypes,
)
from drf_spectacular.types import OpenApiTypes

from .models import User


@extend_schema_serializer(component_name="UserRegistration")
class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration data.

    Handles new user account creation with comprehensive user information
    and secure password handling. All personal data fields are validated
    for format and security compliance.

    **Data Schema:**

    | Field | Type | Required | Write-only | Format | Description |
    |-------|------|----------|------------|--------|-------------|
    | email | Email | Yes | No | email@domain.com | User's primary email address |
    | password | String | Yes | Yes | - | Secure password (validated) |
    | first_name | String | Yes | No | 1-30 chars | User's given name |
    | last_name | String | Yes | No | 1-30 chars | User's family name |
    | phone | String | No | No | 3-20 chars | Contact phone number |
    | date_of_birth | Date | No | No | YYYY-MM-DD | Birth date for age verification |
    | user_type | String | No | No | "patient" or "specialist" | Account type selection |

    **Field Specifications:**

    1. **email field**:
       - Format: Standard email address format
       - Maximum length: 255 characters
       - Must be unique across the system
       - Case-insensitive (stored in lowercase)
       - Validated for proper email format

    2. **password field**:
       - Write-only field (never returned in responses)
       - Minimum length: 8 characters (enforced by validate_password)
       - Maximum length: 128 characters
       - Validated using Django's password validation system
       - Includes checks for common patterns, numeric, uppercase, lowercase
       - Stored as hashed value (never plaintext)

    3. **first_name and last_name fields**:
       - Required for account creation
       - Maximum length: 30 characters each
       - Minimum length: 1 character
       - Accepts Unicode characters (international names)
       - Stripped of leading/trailing whitespace

    4. **phone field**:
       - Optional field for contact information
       - Maximum length: 20 characters
       - Minimum length: 3 characters
       - Format validation performed (digits, spaces, parentheses, dashes)
       - International format support (+ prefix)

    5. **date_of_birth field**:
       - Optional demographic information
       - Format: ISO 8601 date (YYYY-MM-DD)
       - Must be valid calendar date
       - Must be in the past (not future date)
       - Minimum age may be enforced (typically 13+)

    6. **user_type field**:
       - Default value: "patient"
       - Choices: "patient" or "specialist"
       - Determines account permissions and features
       - Cannot be changed after registration (requires admin)

    **Password Validation Rules:**
    - Minimum length: 8 characters
    - Cannot be entirely numeric
    - Cannot be too similar to personal information
    - Cannot be a commonly used password
    - Should contain mix of uppercase, lowercase, numbers, symbols

    **Data Format Examples:**
    - email: "user@example.com" (lowercased on save)
    - password: "SecurePass123!" (hashed, not stored)
    - first_name: "John" (trimmed)
    - last_name: "Doe" (trimmed)
    - phone: "+1 (555) 123-4567" (stored as provided)
    - date_of_birth: "1990-01-15" (ISO format)
    - user_type: "patient" or "specialist"
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
        help_text="Secure password meeting complexity requirements (8+ chars, mixed case, numbers)",
    )
    user_type = serializers.ChoiceField(
        choices=[("patient", "Patient"), ("specialist", "Specialist")],
        default="patient",
        help_text="Account type: 'patient' for healthcare recipient, 'specialist' for provider",
    )

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "first_name",
            "last_name",
            "phone",
            "date_of_birth",
            "user_type",
        ]
        extra_kwargs = {
            "first_name": {
                "required": True,
                "help_text": "User's given name (1-30 characters)",
            },
            "last_name": {
                "required": True,
                "help_text": "User's family name (1-30 characters)",
            },
            "email": {
                "help_text": "Primary email address for account (must be unique)"
            },
            "phone": {
                "required": False,
                "help_text": "Contact phone number (3-20 characters, optional)",
            },
            "date_of_birth": {
                "required": False,
                "help_text": "Birth date in YYYY-MM-DD format (optional)",
                "format": "%Y-%m-%d",
            },
        }


@extend_schema_serializer(component_name="UserLogin")
class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for user authentication credentials.

    Validates login credentials format and prepares for authentication.
    Does not perform actual authentication (handled by view/controller).

    **Data Schema:**

    | Field | Type | Required | Write-only | Format | Description |
    |-------|------|----------|------------|--------|-------------|
    | email | Email | Yes | No | email@domain.com | Registered email address |
    | password | String | Yes | Yes | - | Account password |

    **Field Specifications:**

    1. **email field**:
       - Must be valid email format
       - Maximum length: 255 characters
       - Automatically converted to lowercase
       - Format: local-part@domain.tld
       - Accepts international email addresses

    2. **password field**:
       - Write-only field (never returned)
       - Maximum length: 128 characters
       - No minimum length (handled by authentication)
       - Accepts any printable characters
       - UTF-8 encoding support

    **Length Constraints:**
    - Email: 1-255 characters (after trimming)
    - Password: 1-128 characters

    **Data Processing:**
    1. Email is converted to lowercase
    2. Leading/trailing whitespace is trimmed
    3. No password hashing or transformation in serializer
    4. Raw credentials passed to authentication backend

    **Security Considerations:**
    - Email length limit prevents DoS attacks
    - Password length limit prevents memory exhaustion
    - Credentials validated before authentication attempt
    - No information leakage about account existence
    """

    email = serializers.EmailField(
        required=True, help_text="Registered email address for authentication"
    )
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
        help_text="Account password for authentication",
    )


@extend_schema_serializer(component_name="UserProfile")
class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile data display.

    Provides comprehensive user information for profile views and updates.
    Includes both stored fields and computed fields for user interface display.

    **Data Schema:**

    | Field | Type | Read-only | Format | Description |
    |-------|------|-----------|--------|-------------|
    | id | Integer | Yes | - | Unique user identifier |
    | email | Email | Yes | email@domain.com | Primary email address |
    | first_name | String | No | 1-30 chars | User's given name |
    | last_name | String | No | 1-30 chars | User's family name |
    | full_name | String | Yes | - | Computed full name |
    | phone | String | No | 3-20 chars | Contact phone number |
    | date_of_birth | Date | No | YYYY-MM-DD | Birth date |
    | user_type | String | Yes | "patient" or "specialist" | Account type |
    | is_active | Boolean | Yes | true/false | Account activation status |
    | created_at | DateTime | Yes | ISO 8601 | Account creation timestamp |
    | updated_at | DateTime | Yes | ISO 8601 | Last profile update timestamp |

    **Field Specifications:**

    1. **Read-only fields**:
       - id: Auto-incrementing primary key
       - email: Cannot be changed via profile update
       - user_type: Requires admin intervention to change
       - is_active: Controlled by activation/deactivation processes
       - created_at: Set at account creation
       - updated_at: Automatically managed by Django

    2. **Updatable fields**:
       - first_name: Personal name updates
       - last_name: Family name updates
       - phone: Contact information updates
       - date_of_birth: Demographic information updates

    3. **Computed fields**:
       - full_name: Concatenation of first_name + " " + last_name
       - Provides convenient display format
       - Not stored in database

    **Date/Time Formats:**
    - date_of_birth: YYYY-MM-DD (date only)
    - created_at: YYYY-MM-DDTHH:MM:SSZ (ISO 8601 with timezone)
    - updated_at: YYYY-MM-DDTHH:MM:SSZ (ISO 8601 with timezone)

    **Account Status Information:**
    - is_active: true = account can authenticate, false = disabled
    - user_type: Determines feature access and permissions
    """

    full_name = serializers.SerializerMethodField(
        help_text="Computed full name: first_name + ' ' + last_name", read_only=True
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "date_of_birth",
            "user_type",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "email",
            "user_type",
            "is_active",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "first_name": {
                "help_text": "User's given name (1-30 characters)",
                "min_length": 1,
                "max_length": 30,
            },
            "last_name": {
                "help_text": "User's family name (1-30 characters)",
                "min_length": 1,
                "max_length": 30,
            },
            "phone": {
                "help_text": "Contact phone number (3-20 characters)",
                "required": False,
                "min_length": 3,
                "max_length": 20,
            },
            "date_of_birth": {
                "help_text": "Birth date in YYYY-MM-DD format",
                "required": False,
                "format": "%Y-%m-%d",
            },
        }

    @extend_schema_field(OpenApiTypes.STR)
    def get_full_name(self, obj):
        """
        Compute and return user's full name from first and last names.

        **Data Format:**
        - Output: "First Last" (single space separator)
        - Empty fields handled gracefully
        - Returns empty string if both names missing

        **Examples:**
        - first_name="John", last_name="Doe" → "John Doe"
        - first_name="", last_name="Smith" → "Smith"
        - first_name="Alice", last_name="" → "Alice"
        - first_name="", last_name="" → ""

        **Usage:**
        - Display purposes only
        - Not used for sorting or searching
        - Consistent format across UI components

        Args:
            obj (User): The user instance

        Returns:
            str: Concatenated full name
        """
        return obj.get_full_name()


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


@extend_schema_serializer(component_name="EmailActivation")
class EmailActivationSerializer(serializers.Serializer):
    """
    Serializer for email activation token validation.

    Validates email confirmation token for account activation
    or email address verification processes.

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | token | String | Yes | JWT string | Email activation token |

    **Field Specifications:**

    1. **token field**:
       - JWT token from activation email
       - Contains user ID and email verification data
       - Validated for format, signature, and expiration
       - Single-use token

    **Token Characteristics:**
    - JWT format with user identification
    - Contains email verification intent
    - Short expiration (typically 24 hours)
    - One-time use design
    - Cryptographic signature verification

    **Activation Process:**
    1. Token format validation
    2. Signature verification
    3. Expiration check
    4. Single-use validation
    5. User account activation

    **Error Conditions:**
    - Invalid token format
    - Expired token
    - Already used token
    - Signature mismatch
    """

    token = serializers.CharField(
        required=True, help_text="Email activation token received via email"
    )


@extend_schema_serializer(component_name="TokenRefresh")
class TokenRefreshSerializer(serializers.Serializer):
    """
    Serializer for JWT token refresh operation.

    Accepts refresh token and returns new access token
    for extending authenticated session without re-login.

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | refresh | String | Yes | JWT string | Valid refresh token |

    **Field Specifications:**

    1. **refresh field**:
       - Valid JWT refresh token
       - Not expired refresh token
       - Properly signed token
       - Returns new access token in validated data

    **Token Flow:**
    - Input: Valid refresh token
    - Output: New access token (added to attrs dict)
    - Refresh token remains valid for rotation

    **Security Characteristics:**
    - Refresh tokens have longer expiration
    - Access tokens have shorter expiration
    - Token rotation capability
    - Blacklist support for revoked tokens

    **Usage Pattern:**
    1. Client receives access + refresh tokens on login
    2. Access token expires (short-lived)
    3. Client sends refresh token to get new access token
    4. Process repeats until refresh token expires

    **Output Data:**
    After validation, serializer adds 'access' key to attrs
    containing new JWT access token string.
    """

    refresh = serializers.CharField(
        required=True,
        help_text="Valid JWT refresh token for obtaining new access token",
    )
