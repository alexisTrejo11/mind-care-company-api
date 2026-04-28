from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from drf_spectacular.utils import (
    extend_schema_serializer,
    extend_schema_field,
)
from drf_spectacular.types import OpenApiTypes

from .models import Appointment
from apps.specialists.models import Specialist
from apps.core.exceptions.base_exceptions import (
    NotFoundError,
)
from django.core.exceptions import ValidationError

User = get_user_model()


@extend_schema_serializer(component_name="Appointment")
class AppointmentSerializer(serializers.ModelSerializer):
    """
    Serializer for appointment data display and read operations.

    Provides comprehensive appointment information with related entity references
    and computed display fields. Used for viewing appointment details in the system.

    **Data Schema:**

    | Field | Type | Read-only | Format | Description |
    |-------|------|-----------|--------|-------------|
    | id | Integer | Yes | - | Unique appointment identifier |
    | patient | Integer | No | - | Foreign key to patient user |
    | patient_name | String | Yes | - | Computed patient full name |
    | specialist | Integer | No | - | Foreign key to specialist |
    | specialist_name | String | Yes | - | Computed specialist full name |
    | specialist_specialty | String | Yes | - | Specialist's medical specialization |
    | appointment_type | String | No | "consultation"/"therapy"/"follow_up"/"emergency" | Type of appointment |
    | appointment_date | DateTime | No | ISO 8601 | Scheduled date of appointment |
    | start_time | DateTime | No | ISO 8601 | Appointment start time |
    | end_time | DateTime | No | ISO 8601 | Appointment end time |
    | duration_minutes | Integer | No | 5-480 | Scheduled duration in minutes |
    | status | String | No | "scheduled"/"confirmed"/"in_progress"/"completed"/"cancelled"/"no_show" | Current appointment status |
    | notes | String | No | - | Appointment notes and remarks |
    | symptoms | String | No | - | Patient-reported symptoms |
    | meeting_link | URL | No | - | Virtual meeting URL for online appointments |
    | room_number | String | No | - | Physical room number for in-person appointments |
    | created_at | DateTime | Yes | ISO 8601 | Appointment creation timestamp |
    | updated_at | DateTime | Yes | ISO 8601 | Last update timestamp |

    **Field Specifications:**

    1. **Entity References**:
       - patient: Direct foreign key to patient user
       - patient_name: Computed from user's first/last name
       - specialist: Direct foreign key to specialist
       - specialist_name: Computed from specialist's user profile
       - specialist_specialty: Medical specialization field

    2. **Appointment Scheduling**:
       - appointment_date: Combined date/time field
       - start_time/end_time: Specific time boundaries
       - duration_minutes: Calculated/validated duration
       - appointment_type: Classification of appointment purpose

    3. **Appointment Details**:
       - status: Current workflow state
       - notes: Administrative or clinical notes
       - symptoms: Patient-reported health concerns
       - meeting_link: Virtual appointment URL
       - room_number: Physical location identifier

    4. **Metadata**:
       - created_at/updated_at: Automatic timestamp tracking

    **Appointment Type Options:**
    - "consultation": Initial medical consultation
    - "therapy": Therapeutic treatment session
    - "follow_up": Follow-up appointment
    - "emergency": Urgent care appointment

    **Status Workflow:**
    - "scheduled": Initial booking
    - "confirmed": Patient confirmed
    - "in_progress": Currently happening
    - "completed": Successfully finished
    - "cancelled": Cancelled before start
    - "no_show": Patient didn't attend

    **Time Format:** ISO 8601 with timezone (YYYY-MM-DDTHH:MM:SSZ)
    """

    patient_name = serializers.SerializerMethodField(
        help_text="Full name of the patient (first + last name)", read_only=True
    )
    specialist_name = serializers.SerializerMethodField(
        help_text="Full name of the specialist (first + last name)", read_only=True
    )
    specialist_specialty = serializers.SerializerMethodField(
        help_text="Medical specialization of the specialist", read_only=True
    )

    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient",
            "patient_name",
            "specialist",
            "specialist_name",
            "specialist_specialty",
            "appointment_type",
            "appointment_date",
            "start_time",
            "end_time",
            "duration_minutes",
            "status",
            "notes",
            "symptoms",
            "meeting_link",
            "room_number",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
        extra_kwargs = {
            "patient": {"help_text": "ID of the patient user for this appointment"},
            "specialist": {"help_text": "ID of the specialist for this appointment"},
            "appointment_type": {"help_text": "Classification of appointment purpose"},
            "appointment_date": {
                "help_text": "Scheduled date and time of the appointment"
            },
            "start_time": {"help_text": "Appointment start time"},
            "end_time": {"help_text": "Appointment end time"},
            "duration_minutes": {
                "help_text": "Scheduled duration in minutes (5-480)",
                "min_value": 5,
                "max_value": 480,
            },
            "status": {"help_text": "Current workflow state of the appointment"},
            "notes": {"help_text": "Appointment notes and remarks", "required": False},
            "symptoms": {
                "help_text": "Patient-reported symptoms and concerns",
                "required": False,
            },
            "meeting_link": {
                "help_text": "Virtual meeting URL for online appointments",
                "required": False,
            },
            "room_number": {
                "help_text": "Physical room number for in-person appointments",
                "required": False,
            },
        }


@extend_schema_serializer(component_name="AppointmentCreate")
class AppointmentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new appointment bookings.

    Handles appointment creation with patient/specialist assignment,
    time scheduling, and basic validation. Supports both patient self-booking
    and administrative booking for patients.

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | specialist_id | Integer | Yes | - | ID of the specialist |
    | patient_id | Integer | No | - | ID of the patient (optional for self-booking) |
    | appointment_type | String | No | "consultation"/"therapy"/"follow_up"/"emergency" | Type of appointment (default: "consultation") |
    | appointment_date | DateTime | Yes | ISO 8601 | Scheduled appointment date |
    | start_time | DateTime | Yes | ISO 8601 | Appointment start time |
    | end_time | DateTime | Yes | ISO 8601 | Appointment end time |
    | duration_minutes | Integer | Yes | 5-480 | Scheduled duration in minutes |
    | notes | String | No | - | Initial appointment notes |
    | symptoms | String | No | - | Patient-reported symptoms |
    | meeting_link | URL | No | - | Virtual meeting URL |
    | room_number | String | No | - | Physical room number |

    **Field Specifications:**

    1. **specialist_id field**:
       - Required specialist selection
       - Must reference existing active specialist
       - Specialist must be accepting new patients

    2. **patient_id field**:
       - Optional for patient self-booking
       - Required for administrative booking
       - Must reference existing patient user

    3. **appointment_type field**:
       - Optional type specification
       - Default: "consultation"
       - Determines appointment handling

    4. **Time Scheduling Fields**:
       - appointment_date: Overall appointment date
       - start_time/end_time: Specific time boundaries
       - duration_minutes: Validated against time difference
       - Minimum duration: 5 minutes
       - Maximum duration: 480 minutes (8 hours)

    5. **Additional Details**:
       - notes: Optional administrative notes
       - symptoms: Optional health concerns
       - meeting_link: Optional virtual meeting URL
       - room_number: Optional physical location

    **Patient Assignment Logic:**
    - If patient_id provided: Use specified patient
    - If patient_id not provided: Use authenticated patient user
    - Patients can only book for themselves
    - Staff/admins can book for any patient
    """

    patient_id = serializers.IntegerField(
        required=False,
        help_text="ID of the patient user (optional for patient self-booking)",
    )
    specialist_id = serializers.IntegerField(
        required=True, help_text="ID of the specialist for the appointment"
    )

    class Meta:
        model = Appointment
        fields = [
            "specialist_id",
            "patient_id",
            "appointment_type",
            "appointment_date",
            "start_time",
            "end_time",
            "duration_minutes",
            "notes",
            "symptoms",
            "meeting_link",
            "room_number",
        ]
        extra_kwargs = {
            "appointment_type": {
                "required": False,
                "help_text": "Type of appointment (default: consultation)",
            },
            "appointment_date": {
                "required": True,
                "help_text": "Scheduled date and time for the appointment",
            },
            "start_time": {
                "required": True,
                "help_text": "Appointment start time (must be future)",
            },
            "end_time": {
                "required": True,
                "help_text": "Appointment end time (must be after start_time)",
            },
            "duration_minutes": {
                "required": True,
                "help_text": "Scheduled duration in minutes (5-480)",
                "min_value": 5,
                "max_value": 480,
            },
            "notes": {
                "required": False,
                "help_text": "Initial appointment notes and remarks",
            },
            "symptoms": {
                "required": False,
                "help_text": "Patient-reported symptoms and health concerns",
            },
            "meeting_link": {
                "required": False,
                "help_text": "Virtual meeting URL for online appointments",
            },
            "room_number": {
                "required": False,
                "help_text": "Physical room number for in-person appointments",
            },
        }


@extend_schema_serializer(component_name="AppointmentUpdate")
class AppointmentUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating existing appointment details.

    Allows limited updates to appointment information, primarily focused on
    status changes and additional details. Core scheduling information
    cannot be modified (use reschedule for time changes).

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | status | String | No | "scheduled"/"confirmed"/"in_progress"/"completed"/"cancelled"/"no_show" | Updated appointment status |
    | notes | String | No | - | Updated appointment notes |
    | symptoms | String | No | - | Updated patient symptoms |
    | meeting_link | URL | No | - | Updated virtual meeting URL |
    | room_number | String | No | - | Updated physical room number |

    **Field Specifications:**

    1. **status field**:
       - Optional status update
       - Must follow valid state transitions
       - Cannot revert from completed/cancelled/no_show

    2. **notes field**:
       - Optional notes addition/update
       - Can append to existing notes
       - Supports administrative documentation

    3. **symptoms field**:
       - Optional symptoms update
       - Can be updated before appointment
       - Cleared after appointment completion

    4. **meeting_link field**:
       - Optional virtual meeting URL
       - Typically added before appointment
       - Valid URL format required

    5. **room_number field**:
       - Optional physical location
       - Room assignment for in-person
       - Cleared after appointment

    **Update Restrictions:**
    - Cannot modify: patient, specialist, appointment_type
    - Cannot modify: appointment_date, start_time, end_time, duration_minutes
    - Time changes require reschedule operation
    - Patient/specialist changes require new appointment
    """

    class Meta:
        model = Appointment
        fields = [
            "status",
            "notes",
            "symptoms",
            "meeting_link",
            "room_number",
        ]
        extra_kwargs = {
            "status": {"required": False, "help_text": "Updated appointment status"},
            "notes": {
                "required": False,
                "help_text": "Updated appointment notes and documentation",
            },
            "symptoms": {
                "required": False,
                "help_text": "Updated patient-reported symptoms",
            },
            "meeting_link": {
                "required": False,
                "help_text": "Updated virtual meeting URL",
            },
            "room_number": {
                "required": False,
                "help_text": "Updated physical room assignment",
            },
        }


@extend_schema_serializer(component_name="AppointmentReschedule")
class AppointmentRescheduleSerializer(serializers.Serializer):
    """
    Serializer for appointment rescheduling parameters.

    Handles time and date changes for existing appointments with
    validation of new scheduling parameters and optional rescheduling reason.

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | new_appointment_date | DateTime | Yes | ISO 8601 | New appointment date |
    | new_start_time | DateTime | Yes | ISO 8601 | New start time |
    | new_end_time | DateTime | Yes | ISO 8601 | New end time |
    | new_duration_minutes | Integer | Yes | 5-480 | New duration in minutes |
    | reason | String | No | 0-500 chars | Optional rescheduling reason |

    **Field Specifications:**

    1. **Time/Date Fields**:
       - new_appointment_date: Overall new date
       - new_start_time: Specific new start time
       - new_end_time: Specific new end time
       - new_duration_minutes: New scheduled duration

    2. **reason field**:
       - Optional explanation for rescheduling
       - Maximum length: 500 characters
       - Stored for audit purposes
       - Can include patient/specialist notes

    **Time Validation Rules:**
    1. new_start_time must be before new_end_time
    2. new_appointment_date must match new_start_time.date()
    3. new_start_time must be in the future
    4. new_duration_minutes must match time difference (±1 minute tolerance)
    5. new_duration_minutes must be 5-480 minutes

    **Context Requirements:**
    - Requires appointment context in serializer context
    - appointment: The Appointment instance being rescheduled
    - request: HTTP request for permission checks

    **Rescheduling Constraints:**
    - Cannot reschedule to past times
    - Cannot reschedule completed/cancelled appointments
    - May require specialist availability validation
    - May require minimum notice period
    """

    new_appointment_date = serializers.DateTimeField(
        required=True, help_text="New date for the rescheduled appointment"
    )
    new_start_time = serializers.DateTimeField(
        required=True, help_text="New start time for the rescheduled appointment"
    )
    new_end_time = serializers.DateTimeField(
        required=True, help_text="New end time for the rescheduled appointment"
    )
    new_duration_minutes = serializers.IntegerField(
        min_value=5,
        help_text="New duration in minutes for the rescheduled appointment (5-480)",
    )
    reason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="Optional reason for rescheduling the appointment",
    )


@extend_schema_serializer(component_name="AppointmentStats")
class AppointmentStatsSerializer(serializers.Serializer):
    """
    Serializer for appointment statistics query parameters.

    Defines parameters for retrieving appointment analytics and statistics
    with temporal filtering and specialist-specific options.

    **Data Schema:**

    | Field | Type | Required | Default | Format | Description |
    |-------|------|----------|---------|--------|-------------|
    | period | String | Yes | - | "today"/"week"/"month"/"year"/"custom" | Time period for statistics |
    | start_date | Date | No | - | YYYY-MM-DD | Custom period start date |
    | end_date | Date | No | - | YYYY-MM-DD | Custom period end date |
    | specialist_id | Integer | No | - | - | Filter by specific specialist |

    **Period Options:**

    1. **"today"**: Statistics for current calendar day
    2. **"week"**: Statistics for current calendar week (Monday-Sunday)
    3. **"month"**: Statistics for current calendar month
    4. **"year"**: Statistics for current calendar year
    5. **"custom"**: User-defined date range (requires start_date and end_date)

    **Field Specifications:**

    1. **period field**:
       - Required time period selection
       - Determines date range calculation
       - "custom" enables explicit date range

    2. **start_date and end_date fields**:
       - Required only for period="custom"
       - start_date must be ≤ end_date
       - Inclusive date range [start_date, end_date]
       - Format: YYYY-MM-DD (date only)

    3. **specialist_id field**:
       - Optional specialist filter
       - Limits statistics to specific provider
       - If omitted, includes all specialists

    **Statistics Output:**
    - Appointment counts by status
    - Duration totals and averages
    - Type distribution
    - Specialist performance metrics
    - Time slot utilization rates
    """

    period = serializers.ChoiceField(
        choices=["today", "week", "month", "year", "custom"],
        required=True,
        help_text="Time period for statistics aggregation",
    )
    start_date = serializers.DateField(
        required=False,
        help_text="Start date for custom period (required when period='custom')",
        format="%Y-%m-%d",
    )
    end_date = serializers.DateField(
        required=False,
        help_text="End date for custom period (required when period='custom')",
        format="%Y-%m-%d",
    )
    specialist_id = serializers.IntegerField(
        required=False,
        help_text="Filter statistics by specific specialist ID (optional)",
    )
