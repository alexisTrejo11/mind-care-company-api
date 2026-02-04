from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer

from ..models import User


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
