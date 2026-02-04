from rest_framework import serializers
from drf_spectacular.utils import (
    extend_schema_serializer,
    extend_schema_field,
    OpenApiExample,
)
from drf_spectacular.types import OpenApiTypes

from ..models import Availability


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Recurring Availability",
            description="Recurring weekly availability for Mondays",
            value={
                "id": 1,
                "day_of_week": 1,
                "day_name": "Monday",
                "start_time": "09:00:00",
                "end_time": "17:00:00",
                "is_recurring": True,
                "valid_from": "2024-01-01",
                "valid_until": None,
            },
            response_only=True,
        ),
        OpenApiExample(
            "Temporary Availability",
            description="One-time availability for a specific date range",
            value={
                "id": 2,
                "day_of_week": 3,
                "day_name": "Wednesday",
                "start_time": "10:00:00",
                "end_time": "15:00:00",
                "is_recurring": False,
                "valid_from": "2024-12-01",
                "valid_until": "2024-12-31",
            },
            response_only=True,
        ),
        OpenApiExample(
            "Weekend Availability",
            description="Saturday availability with recurring schedule",
            value={
                "id": 3,
                "day_of_week": 6,
                "day_name": "Saturday",
                "start_time": "08:00:00",
                "end_time": "12:00:00",
                "is_recurring": True,
                "valid_from": "2024-01-01",
                "valid_until": None,
            },
            response_only=True,
        ),
    ]
)
class AvailabilitySerializer(serializers.ModelSerializer):
    """
    Serializer for specialist availability schedule data.

    Represents time periods when a healthcare specialist is available for appointments.
    Manages both recurring weekly schedules and temporary/one-time availability.

    **Data Schema:**

    | Field | Type | Format | Required | Read-only | Description |
    |-------|------|--------|----------|-----------|-------------|
    | id | Integer | - | No | Yes | Unique identifier for the availability record |
    | day_of_week | Integer | 0-6 | Yes | No | Day of week (0=Sunday, 6=Saturday) |
    | day_name | String | - | No | Yes | Human-readable day name (derived from day_of_week) |
    | start_time | Time | HH:MM:SS | Yes | No | Start time of availability slot |
    | end_time | Time | HH:MM:SS | Yes | No | End time of availability slot |
    | is_recurring | Boolean | - | Yes | No | Whether this availability repeats weekly |
    | valid_from | Date | YYYY-MM-DD | Yes | No | Date when availability becomes effective |
    | valid_until | Date | YYYY-MM-DD | No | No | Date when availability expires (null = indefinite) |

    **Day of Week Mapping:**

    | Integer | Day Name | ISO Standard |
    |---------|----------|--------------|
    | 0 | Sunday | Start of week (US) |
    | 1 | Monday | Start of week (ISO) |
    | 2 | Tuesday | - |
    | 3 | Wednesday | - |
    | 4 | Thursday | - |
    | 5 | Friday | - |
    | 6 | Saturday | End of week |

    **Time Format:**
    - Format: 24-hour clock (HH:MM:SS)
    - Examples: "09:00:00", "14:30:00", "17:45:00"
    - Timezone: Stored in UTC, displayed in specialist's local timezone

    **Date Format:**
    - Format: ISO 8601 (YYYY-MM-DD)
    - Examples: "2024-01-15", "2024-12-31"
    - Timezone: Date-only (no time component)

    **Field Constraints and Validation:**

    1. **day_of_week**:
       - Integer between 0 and 6 inclusive
       - Maps to specific days (see mapping above)

    2. **start_time and end_time**:
       - Must be valid time values
       - end_time must be later than start_time
       - Minimum slot duration: 15 minutes
       - Maximum slot duration: 12 hours
       - Business hours typically 08:00-20:00

    3. **is_recurring flag**:
       - `True`: Repeats every week on specified day
       - `False`: One-time availability for specific date(s)

    4. **valid_from and valid_until**:
       - valid_from is required
       - valid_until can be null for indefinite recurrence
       - If valid_until is provided, must be after valid_from
       - Dates cannot be in the past when creating

    5. **Date and Time Consistency**:
       - Recurring availability: Uses day_of_week, ignores specific dates
       - Non-recurring: Uses exact dates from valid_from to valid_until

    **Data Display Characteristics:**

    1. **day_name field**:
       - Computed field derived from day_of_week
       - Provides human-readable day name
       - Uses Django's get_FOO_display() pattern
       - Read-only (not accepted in input)

    2. **Time Representation**:
       - Times are formatted as strings in HH:MM:SS
       - Frontend can parse for time pickers
       - Supports 15-minute intervals (common for appointments)

    3. **Date Representation**:
       - Dates formatted as YYYY-MM-DD strings
       - Null values represented as null/None in JSON

    4. **Boolean Representation**:
       - is_recurring: true/false in JSON
       - Default depends on use case

    **Example Data Structures:**

    ```json
    // Recurring weekly availability (every Monday 9-5)
    {
        "id": 1,
        "day_of_week": 1,
        "day_name": "Monday",
        "start_time": "09:00:00",
        "end_time": "17:00:00",
        "is_recurring": true,
        "valid_from": "2024-01-01",
        "valid_until": null
    }

    // Temporary availability (specific date range)
    {
        "id": 2,
        "day_of_week": 3,
        "day_name": "Wednesday",
        "start_time": "10:00:00",
        "end_time": "15:00:00",
        "is_recurring": false,
        "valid_from": "2024-12-01",
        "valid_until": "2024-12-31"
    }

    // Weekend availability (Saturdays only)
    {
        "id": 3,
        "day_of_week": 6,
        "day_name": "Saturday",
        "start_time": "08:00:00",
        "end_time": "12:00:00",
        "is_recurring": true,
        "valid_from": "2024-01-01",
        "valid_until": "2024-12-31"
    }
    ```

    **Common Data Patterns:**

    1. **Standard Work Week**:
       - Monday-Friday, 9AM-5PM
       - is_recurring: true
       - valid_until: null (indefinite)

    2. **Part-time Schedule**:
       - Specific days with custom hours
       - May have different hours per day

    3. **Seasonal Availability**:
       - is_recurring: true
       - valid_until set to season end date

    4. **Vacation Coverage**:
       - is_recurring: false
       - Specific date range with adjusted hours

    **Data Integrity Rules:**

    1. No overlapping availability slots for same specialist
    2. Availability must be within reasonable hours (e.g., 6AM-10PM)
    3. Minimum appointment duration considered in slot creation
    4. Timezone consistency maintained across all records

    **Related Data Models:**
    - Links to Specialist model via foreign key
    - Used by Appointment model for scheduling
    - Referenced by Calendar display systems
    """

    day_name = serializers.SerializerMethodField(
        help_text="Human-readable name of the day derived from day_of_week",
        read_only=True,
    )

    class Meta:
        model = Availability
        fields = [
            "id",
            "day_of_week",
            "day_name",
            "start_time",
            "end_time",
            "is_recurring",
            "valid_from",
            "valid_until",
        ]
        read_only_fields = ["id", "day_name"]
        extra_kwargs = {
            "day_of_week": {
                "help_text": "Day of week as integer (0=Sunday, 1=Monday, ..., 6=Saturday)",
                "min_value": 0,
                "max_value": 6,
            },
            "start_time": {
                "help_text": "Start time of availability in HH:MM:SS format",
                "format": "%H:%M:%S",
            },
            "end_time": {
                "help_text": "End time of availability in HH:MM:SS format",
                "format": "%H:%M:%S",
            },
            "is_recurring": {
                "help_text": "True: repeats weekly, False: specific date range only",
                "default": True,
            },
            "valid_from": {
                "help_text": "Date when this availability becomes effective (YYYY-MM-DD)",
                "format": "%Y-%m-%d",
            },
            "valid_until": {
                "help_text": "Date when this availability expires (null = indefinite)",
                "format": "%Y-%m-%d",
                "required": False,
                "allow_null": True,
            },
        }

    @extend_schema_field(OpenApiTypes.STR)
    def get_day_name(self, obj):
        """
        Get the human-readable day name from the day_of_week integer.

        **Data Transformation:**
        - Input: Integer (0-6)
        - Output: String day name

        **Mapping Table:**
        - 0 → "Sunday"
        - 1 → "Monday"
        - 2 → "Tuesday"
        - 3 → "Wednesday"
        - 4 → "Thursday"
        - 5 → "Friday"
        - 6 → "Saturday"

        **Implementation Details:**
        - Uses Django's get_FOO_display() pattern
        - Returns localized day name if Django localization is enabled
        - Read-only field for display purposes only

        **Example:**
        ```python
        # For day_of_week = 1
        get_day_name() → "Monday"

        # For day_of_week = 6
        get_day_name() → "Saturday"
        ```

        **Data Consistency:**
        - Always matches the day_of_week value
        - Provides user-friendly display
        - Not used for sorting or filtering (use day_of_week instead)

        Args:
            obj (Availability): The availability instance

        Returns:
            str: Display name of the day of week
        """
        return obj.get_day_of_week_display()
