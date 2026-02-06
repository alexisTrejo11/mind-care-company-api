from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from drf_spectacular.utils import extend_schema_serializer, extend_schema_field
from drf_spectacular.types import OpenApiTypes

from .models import MedicalRecord
from apps.appointments.models import Appointment
from django.core.exceptions import ValidationError, ObjectDoesNotExist

User = get_user_model()


@extend_schema_serializer(component_name="MedicalRecord")
class MedicalRecordSerializer(serializers.ModelSerializer):
    """
    Serializer for medical record data display and read operations.

    Provides comprehensive medical record information with related entity references
    and computed display fields. All fields are read-only in this serializer.

    **Data Schema:**

    | Field | Type | Read-only | Source | Format | Description |
    |-------|------|-----------|--------|--------|-------------|
    | id | Integer | Yes | - | - | Unique medical record identifier |
    | patient_id | Integer | Yes | patient.id | - | Foreign key to patient user |
    | patient_name | String | Yes | patient.get_full_name() | - | Patient's full name |
    | specialist_id | Integer | Yes | specialist.id | - | Foreign key to specialist |
    | specialist_name | String | Yes | specialist.user.get_full_name() | - | Specialist's full name |
    | appointment_id | Integer | Yes | appointment.id | - | Foreign key to appointment |
    | appointment_date | DateTime | Yes | appointment.appointment_date | ISO 8601 | Original appointment date/time |
    | diagnosis | String | Yes | - | - | Medical diagnosis details |
    | prescription | String | Yes | - | - | Medication/treatment prescriptions |
    | notes | String | Yes | - | - | Clinical notes and observations |
    | recommendations | String | Yes | - | - | Treatment recommendations |
    | follow_up_date | Date | Yes | - | YYYY-MM-DD | Recommended follow-up date |
    | confidentiality_level | String | Yes | - | "standard"/"sensitive"/"highly_sensitive" | Data sensitivity level |
    | confidentiality_display | String | Yes | get_confidentiality_level_display() | "Standard"/"Sensitive"/"Highly Sensitive" | Human-readable confidentiality level |
    | created_at | DateTime | Yes | - | ISO 8601 | Record creation timestamp |
    | updated_at | DateTime | Yes | - | ISO 8601 | Last update timestamp |

    **Field Specifications:**

    1. **Referenced Entity Fields**:
       - patient_id/specialist_id/appointment_id: Foreign key references
       - patient_name/specialist_name: Computed full names for display
       - appointment_date: Date/time of original consultation

    2. **Medical Content Fields**:
       - diagnosis: Required field containing medical diagnosis
       - prescription: Optional medication/treatment instructions
       - notes: Optional clinical observations
       - recommendations: Optional treatment/next-step recommendations
       - follow_up_date: Optional future date for next appointment

    3. **Metadata Fields**:
       - confidentiality_level: Data sensitivity classification
       - confidentiality_display: Human-readable confidentiality label
       - created_at/updated_at: Automatic timestamp tracking

    **Confidentiality Levels:**
    - "standard": Routine medical information
    - "sensitive": Sensitive health information
    - "highly_sensitive": Highly protected health information

    **Timestamp Formats:**
    - appointment_date: YYYY-MM-DDTHH:MM:SSZ (with timezone)
    - created_at/updated_at: YYYY-MM-DDTHH:MM:SSZ (with timezone)
    - follow_up_date: YYYY-MM-DD (date only)

    **Display Fields:**
    - patient_name: Concatenated first + last name
    - specialist_name: Concatenated first + last name
    - confidentiality_display: Title-cased confidentiality level
    """

    patient_id = serializers.IntegerField(
        source="patient.id",
        read_only=True,
        help_text="ID of the patient user associated with this medical record",
    )
    patient_name = serializers.CharField(
        source="patient.get_full_name",
        read_only=True,
        help_text="Full name of the patient (first + last name)",
    )

    specialist_id = serializers.IntegerField(
        source="specialist.id",
        read_only=True,
        help_text="ID of the specialist who created this medical record",
    )
    specialist_name = serializers.CharField(
        source="specialist.user.get_full_name",
        read_only=True,
        help_text="Full name of the specialist (first + last name)",
    )

    appointment_id = serializers.IntegerField(
        source="appointment.id",
        read_only=True,
        help_text="ID of the appointment that generated this medical record",
    )
    appointment_date = serializers.DateTimeField(
        source="appointment.appointment_date",
        read_only=True,
        help_text="Date and time of the original appointment",
    )

    confidentiality_display = serializers.CharField(
        source="get_confidentiality_level_display",
        read_only=True,
        help_text="Human-readable confidentiality level display",
    )

    class Meta:
        model = MedicalRecord
        fields = [
            "id",
            "patient_id",
            "patient_name",
            "specialist_id",
            "specialist_name",
            "appointment_id",
            "appointment_date",
            "diagnosis",
            "prescription",
            "notes",
            "recommendations",
            "follow_up_date",
            "confidentiality_level",
            "confidentiality_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "diagnosis": {"help_text": "Medical diagnosis and assessment details"},
            "prescription": {
                "help_text": "Medications, treatments, or therapy prescriptions"
            },
            "notes": {"help_text": "Clinical notes, observations, and remarks"},
            "recommendations": {
                "help_text": "Treatment recommendations and next steps"
            },
            "follow_up_date": {
                "help_text": "Recommended date for follow-up appointment",
                "format": "%Y-%m-%d",
            },
            "confidentiality_level": {
                "help_text": "Data sensitivity classification level"
            },
            "created_at": {"help_text": "Timestamp when medical record was created"},
            "updated_at": {
                "help_text": "Timestamp when medical record was last updated"
            },
        }


@extend_schema_serializer(component_name="MedicalRecordCreate")
class MedicalRecordCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for medical record creation with appointment linkage.

    Handles creation of new medical records with mandatory appointment reference
    and comprehensive medical content validation. All fields are write-only.

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | appointment_id | Integer | Yes | - | ID of associated appointment |
    | diagnosis | String | Yes | - | Medical diagnosis (min 10 chars) |
    | prescription | String | No | - | Treatment prescriptions (min 5 chars if provided) |
    | notes | String | No | - | Clinical notes (min 5 chars if provided) |
    | recommendations | String | No | - | Treatment recommendations |
    | follow_up_date | Date | No | YYYY-MM-DD | Future follow-up date |
    | confidentiality_level | String | No | "standard"/"sensitive"/"highly_sensitive" | Data sensitivity (default: "standard") |

    **Field Specifications:**

    1. **appointment field**:
       - Must reference an existing appointment id
       - Appointment must be completed
       - Links medical record to specific consultation

    2. **diagnosis field**:
       - Required medical assessment
       - Minimum length: 10 characters
       - Should contain specific medical terminology
       - Supports multiline text

    3. **prescription field**:
       - Optional medication instructions
       - If provided, minimum 5 characters
       - Can include dosage, frequency, duration
       - Supports multiline formatting

    4. **notes field**:
       - Optional clinical observations
       - If provided, minimum 5 characters
       - Can include examination findings
       - Supports multiline text

    5. **recommendations field**:
       - Optional treatment advice
       - No minimum length requirement
       - Can include lifestyle changes, referrals
       - Supports multiline text

    6. **follow_up_date field**:
       - Optional future date
       - Must be today or in the future
       - Format: YYYY-MM-DD
       - Typically 1-12 weeks in future

    7. **confidentiality_level field**:
       - Default: "standard"
       - Choices match CONFIDENTIALITY_CHOICES
       - Determines access restrictions
    """

    class Meta:
        model = MedicalRecord
        fields = [
            "appointment",
            "diagnosis",
            "prescription",
            "notes",
            "recommendations",
            "follow_up_date",
            "confidentiality_level",
        ]
        extra_kwargs = {
            "diagnosis": {
                "required": True,
                "help_text": "Medical diagnosis (minimum 10 characters)",
            },
            "prescription": {
                "required": False,
                "help_text": "Treatment prescriptions (optional, minimum 5 characters if provided)",
            },
            "notes": {
                "required": False,
                "help_text": "Clinical notes and observations (optional, minimum 5 characters if provided)",
            },
            "recommendations": {
                "required": False,
                "help_text": "Treatment recommendations and next steps",
            },
            "follow_up_date": {
                "required": False,
                "help_text": "Recommended follow-up date (must be future date)",
                "format": "%Y-%m-%d",
            },
            "confidentiality_level": {
                "default": "standard",
                "help_text": "Data confidentiality level (default: standard)",
            },
        }

    def validate_prescription(self, value):
        if value and (len(value.strip()) < 4 or len(value.strip()) > 1000):
            raise serializers.ValidationError(
                "Prescription must be between 4 and 1000 characters if provided."
            )
        return value

    def validate_notes(self, value):
        if value and (len(value.strip()) < 4 or len(value.strip()) > 2000):
            raise serializers.ValidationError(
                "Notes must be between 4 and 2000 characters if provided."
            )
        return value

    def validate_follow_up_date(self, value):
        if value and value < timezone.now().date():
            raise serializers.ValidationError(
                "Follow-up date must be today or a future date."
            )
        return value


@extend_schema_serializer(component_name="MedicalRecordUpdate")
class MedicalRecordUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for medical record updates with restricted field set.

    Allows updates to medical content fields while preserving metadata
    and relationships. Updates are limited to content fields only.

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | diagnosis | String | Yes | - | Updated diagnosis (min 10 chars) |
    | prescription | String | No | - | Updated prescriptions |
    | notes | String | No | - | Updated clinical notes |
    | recommendations | String | No | - | Updated recommendations |
    | follow_up_date | Date | No | YYYY-MM-DD | Updated follow-up date |

    **Field Specifications:**

    1. **diagnosis field**:
       - Required even in updates
       - Minimum length: 10 characters
       - Full replacement (not partial update)
       - Previous diagnosis preserved in audit trail

    2. **prescription field**:
       - Optional medication updates
       - Can be cleared by providing empty string
       - Previous prescriptions preserved in audit

    3. **notes field**:
       - Optional notes updates
       - Can be appended or replaced
       - Previous notes preserved in audit

    4. **recommendations field**:
       - Optional recommendations updates
       - Can include new advice or modifications
       - Previous recommendations preserved

    5. **follow_up_date field**:
       - Optional date update
       - Must be today or in the future
       - Can be cleared by providing null
    """

    class Meta:
        model = MedicalRecord
        fields = [
            "diagnosis",
            "prescription",
            "notes",
            "recommendations",
            "follow_up_date",
        ]
        extra_kwargs = {
            "diagnosis": {
                "required": True,
                "help_text": "Updated medical diagnosis (minimum 10 characters)",
            },
            "prescription": {
                "required": False,
                "help_text": "Updated treatment prescriptions",
            },
            "notes": {
                "required": False,
                "help_text": "Updated clinical notes and observations",
            },
            "recommendations": {
                "required": False,
                "help_text": "Updated treatment recommendations",
            },
            "follow_up_date": {
                "required": False,
                "help_text": "Updated follow-up date (must be future date)",
                "format": "%Y-%m-%d",
            },
        }


@extend_schema_serializer(component_name="MedicalRecordFilter")
class MedicalRecordFilterSerializer(serializers.Serializer):
    """
    Serializer for medical record search and filtering parameters.

    Defines parameters for querying and filtering medical records
    with pagination and sorting capabilities.

    **Data Schema:**

    | Field | Type | Required | Default | Format | Description |
    |-------|------|----------|---------|--------|-------------|
    | patient_id | Integer | No | - | - | Filter by specific patient |
    | specialist_id | Integer | No | - | - | Filter by specific specialist |
    | appointment_id | Integer | No | - | - | Filter by specific appointment |
    | confidentiality_level | String | No | - | "standard"/"sensitive"/"highly_sensitive" | Filter by confidentiality level |
    | start_date | Date | No | - | YYYY-MM-DD | Filter records created on or after date |
    | end_date | Date | No | - | YYYY-MM-DD | Filter records created on or before date |
    | has_follow_up | Boolean | No | - | true/false | Filter records with/without follow-up date |
    | search | String | No | - | 1-100 chars | Text search in diagnosis/prescription/notes |
    | page | Integer | No | 1 | 1+ | Page number for pagination |
    | page_size | Integer | No | 20 | 1-100 | Items per page |
    | ordering | String | No | "-created_at" | see choices | Sort order for results |

    **Filtering Options:**

    1. **Entity Filters**:
       - patient_id: Filter by specific patient
       - specialist_id: Filter by specific healthcare provider
       - appointment_id: Filter by specific consultation

    2. **Date Range Filters**:
       - start_date: Minimum creation date
       - end_date: Maximum creation date
       - Uses created_at timestamp

    3. **Content Filters**:
       - confidentiality_level: Data sensitivity filter
       - has_follow_up: Presence of follow-up date
       - search: Text search in medical content

    4. **Pagination Controls**:
       - page: 1-based page number
       - page_size: Items per page (1-100)

    5. **Sorting Options**:
       - "created_at": Oldest first
       - "-created_at": Newest first (default)
       - "follow_up_date": Earliest follow-up first
       - "-follow_up_date": Latest follow-up first
    """

    patient_id = serializers.IntegerField(
        required=False, help_text="Filter by specific patient ID"
    )
    specialist_id = serializers.IntegerField(
        required=False, help_text="Filter by specific specialist ID"
    )
    appointment_id = serializers.IntegerField(
        required=False, help_text="Filter by specific appointment ID"
    )
    confidentiality_level = serializers.ChoiceField(
        choices=MedicalRecord.CONFIDENTIALITY_CHOICES,
        required=False,
        help_text="Filter by data confidentiality level",
    )
    start_date = serializers.DateField(
        required=False,
        help_text="Filter records created on or after this date",
        format="%Y-%m-%d",
    )
    end_date = serializers.DateField(
        required=False,
        help_text="Filter records created on or before this date",
        format="%Y-%m-%d",
    )
    has_follow_up = serializers.BooleanField(
        required=False,
        help_text="Filter records with follow-up date (true) or without (false)",
    )
    search = serializers.CharField(
        required=False,
        max_length=100,
        help_text="Text search in diagnosis, prescription, and notes fields",
    )
    page = serializers.IntegerField(
        min_value=1, default=1, help_text="Page number for pagination (1-based)"
    )
    page_size = serializers.IntegerField(
        min_value=1,
        max_value=100,
        default=20,
        help_text="Number of items per page (maximum 100)",
    )
    ordering = serializers.ChoiceField(
        choices=["created_at", "-created_at", "follow_up_date", "-follow_up_date"],
        required=False,
        default="-created_at",
        help_text="Sort order for results ('-' prefix for descending)",
    )


@extend_schema_serializer(component_name="MedicalRecordExport")
class MedicalRecordExportSerializer(serializers.Serializer):
    """
    Serializer for medical record export configuration parameters.

    Defines parameters for exporting medical records in various formats
    with content customization options.

    **Data Schema:**

    | Field | Type | Required | Default | Format | Description |
    |-------|------|----------|---------|--------|-------------|
    | format | String | No | "pdf" | "pdf"/"csv"/"json" | Export file format |
    | start_date | Date | Yes | - | YYYY-MM-DD | Start date for records inclusion |
    | end_date | Date | Yes | - | YYYY-MM-DD | End date for records inclusion |
    | include_prescriptions | Boolean | No | true | true/false | Include prescription data |
    | include_notes | Boolean | No | true | true/false | Include clinical notes |
    | patient_id | Integer | No | - | - | Filter by specific patient |

    **Export Format Options:**

    1. **PDF Format**:
       - Structured document with formatting
       - Suitable for printing
       - Includes headers/footers

    2. **CSV Format**:
       - Comma-separated values
       - Suitable for data analysis
       - Machine-readable format

    3. **JSON Format**:
       - Structured data format
       - Suitable for system integration
       - Preserves data relationships

    **Content Inclusion Options:**

    1. **include_prescriptions**:
       - true: Include prescription field
       - false: Exclude prescription data

    2. **include_notes**:
       - true: Include clinical notes
       - false: Exclude notes for brevity

    3. **patient_id**:
       - Optional patient filter
       - If omitted, exports all matching records

    **Date Range Requirements:**
    - start_date must be before or equal to end_date
    - Both dates required for export boundary
    - Uses created_at field for filtering
    """

    format = serializers.ChoiceField(
        choices=["pdf", "csv", "json"],
        default="pdf",
        help_text="Export file format selection",
    )
    start_date = serializers.DateField(
        required=True,
        help_text="Start date for records inclusion (inclusive)",
        format="%Y-%m-%d",
    )
    end_date = serializers.DateField(
        required=True,
        help_text="End date for records inclusion (inclusive)",
        format="%Y-%m-%d",
    )
    include_prescriptions = serializers.BooleanField(
        default=True, help_text="Include prescription data in export"
    )
    include_notes = serializers.BooleanField(
        default=True, help_text="Include clinical notes in export"
    )
    patient_id = serializers.IntegerField(
        required=False, help_text="Filter exports to specific patient (optional)"
    )


@extend_schema_serializer(component_name="MedicalRecordAudit")
class MedicalRecordAuditSerializer(serializers.Serializer):
    """
    Serializer for medical record audit log query parameters.

    Defines parameters for querying medical record access and modification
    audit trails with temporal and entity filtering.

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | patient_id | Integer | No | - | Filter by patient |
    | specialist_id | Integer | No | - | Filter by specialist |
    | action | String | No | "view"/"create"/"update"/"export" | Filter by audit action type |
    | start_date | DateTime | No | ISO 8601 | Filter audits on or after timestamp |
    | end_date | DateTime | No | ISO 8601 | Filter audits on or before timestamp |

    **Audit Action Types:**

    1. **view**: Record was viewed/accessed
    2. **create**: Record was created
    3. **update**: Record was modified
    4. **export**: Record was exported

    **Filtering Combinations:**

    1. **Entity-based filtering**:
       - patient_id: Track specific patient's record access
       - specialist_id: Track specific provider's actions

    2. **Action-based filtering**:
       - action: Filter by specific operation type
       - Can combine with entity filters

    3. **Temporal filtering**:
       - start_date: Minimum timestamp
       - end_date: Maximum timestamp
       - Both optional, but if both provided: start_date ≤ end_date

    **Time Range Considerations:**
    - Dates include time component
    - Uses audit event timestamp
    - Timezone-aware comparisons
    - Default range: last 30 days if unspecified
    """

    patient_id = serializers.IntegerField(
        required=False, help_text="Filter audit logs by specific patient ID"
    )
    specialist_id = serializers.IntegerField(
        required=False, help_text="Filter audit logs by specific specialist ID"
    )
    action = serializers.ChoiceField(
        choices=["view", "create", "update", "export"],
        required=False,
        help_text="Filter by specific audit action type",
    )
    start_date = serializers.DateTimeField(
        required=False,
        help_text="Filter audit logs on or after this timestamp",
        format="iso",
    )
    end_date = serializers.DateTimeField(
        required=False,
        help_text="Filter audit logs on or before this timestamp",
        format="iso",
    )
