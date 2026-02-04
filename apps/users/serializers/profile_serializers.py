from rest_framework import serializers
from drf_spectacular.utils import (
    extend_schema_serializer,
    extend_schema_field,
)
from drf_spectacular.types import OpenApiTypes
from ..models import User


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
