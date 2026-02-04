from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.validators import validate_email

from drf_spectacular.utils import (
    extend_schema_serializer,
    extend_schema_field,
    OpenApiExample,
)
from drf_spectacular.types import OpenApiTypes

from ..models import Specialist, SpecialistService, Service
from .service_serializers import ServiceSerializer
from .availability_serializers import AvailabilitySerializer


User = get_user_model()


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Specialist List Item",
            description="Example of a specialist in listing view",
            value={
                "id": 1,
                "specialist_name": "Dr. Jane Smith",
                "license_number": "MD123456",
                "bio": "Board-certified psychiatrist with 10+ years of experience...",
                "specialization": "psychiatrist",
                "years_experience": 10,
                "consultation_fee": "150.00",
                "is_accepting_new_patients": True,
                "rating": "4.8",
                "email": "dr.smith@example.com",
                "phone": "+1234567890",
                "service_count": 5,
            },
            response_only=True,
        ),
        OpenApiExample(
            "Specialist with Rating",
            description="Specialist with high rating",
            value={
                "id": 2,
                "specialist_name": "Dr. John Doe",
                "license_number": "PSY789012",
                "bio": "Cognitive behavioral therapy specialist...",
                "specialization": "psychologist",
                "years_experience": 8,
                "consultation_fee": "120.00",
                "is_accepting_new_patients": True,
                "rating": "4.9",
                "email": "dr.doe@example.com",
                "phone": "+0987654321",
                "service_count": 3,
            },
            response_only=True,
        ),
    ]
)
class SpecialistSerializer(serializers.ModelSerializer):
    """
    Serializer for listing and basic specialist information.

    Used in list views where only essential information is required.

    **Fields Description:**

    | Field | Type | Description |
    |-------|------|-------------|
    | id | Integer | Unique identifier for the specialist |
    | specialist_name | String | Full name (first + last) of the specialist |
    | license_number | String | Professional medical license number |
    | bio | String | Professional biography and background |
    | specialization | String | Medical specialization area |
    | years_experience | Integer | Number of years of professional experience |
    | consultation_fee | Decimal | Fee for initial consultation (in local currency) |
    | is_accepting_new_patients | Boolean | Whether currently accepting new patients |
    | rating | Decimal | Average patient rating (0.00 - 5.00) |
    | email | String | Contact email address |
    | phone | String | Contact phone number |
    | service_count | Integer | Number of services offered by the specialist |

    **Specialization Choices:**

    - `psychologist`: Psychologist
    - `psychiatrist`: Psychiatrist
    - `therapist`: Therapist
    - `counselor`: Counselor
    - `general_physician`: General Physician
    - `nutritionist`: Nutritionist
    - `physiotherapist`: Physiotherapist
    - `neurologist`: Neurologist
    - `other`: Other
    """

    specialist_name = serializers.SerializerMethodField(
        help_text="Full name of the specialist (first name + last name)"
    )
    email = serializers.SerializerMethodField(
        help_text="Email address for contacting the specialist"
    )
    phone = serializers.SerializerMethodField(
        help_text="Phone number for appointments and inquiries"
    )
    service_count = serializers.SerializerMethodField(
        help_text="Number of healthcare services offered by this specialist"
    )

    class Meta:
        model = Specialist
        fields = [
            "id",
            "specialist_name",
            "license_number",
            "bio",
            "specialization",
            "years_experience",
            "consultation_fee",
            "is_accepting_new_patients",
            "rating",
            "email",
            "phone",
            "service_count",
        ]
        read_only_fields = [
            "id",
            "specialist_name",
            "email",
            "phone",
            "service_count",
            "rating",
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_specialist_name(self, obj):
        """
        Get the full name of the specialist.

        Returns:
            str: Combined first and last name, or None if user doesn't exist
        """
        return obj.user.get_full_name() if obj.user else None

    @extend_schema_field(OpenApiTypes.EMAIL)
    def get_email(self, obj):
        """
        Get the specialist's email address.

        Returns:
            str: Email address, or None if user doesn't exist
        """
        return obj.user.email if obj.user else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_phone(self, obj):
        """
        Get the specialist's phone number.

        Returns:
            str: Phone number, or None if not available
        """
        return getattr(obj.user, "phone", None) if obj.user else None

    @extend_schema_field(OpenApiTypes.INT)
    def get_service_count(self, obj):
        """
        Count the number of active services offered by the specialist.

        Returns:
            int: Number of available services
        """
        return obj.services.filter(is_available=True).count()


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Specialist Detail",
            description="Complete specialist profile with nested relationships",
            value={
                "id": 1,
                "user_info": {
                    "full_name": "Dr. Jane Smith",
                    "email": "dr.smith@example.com",
                    "phone": "+1234567890",
                },
                "license_number": "MD123456",
                "specialization": "psychiatrist",
                "qualifications": "MD, Board Certified Psychiatrist, XYZ University",
                "years_experience": 10,
                "consultation_fee": "150.00",
                "is_accepting_new_patients": True,
                "bio": "Board-certified psychiatrist specializing in adult mental health...",
                "rating": "4.8",
                "services": [
                    {
                        "id": 101,
                        "service_details": {
                            "id": 1,
                            "name": "Psychiatric Evaluation",
                            "description": "Initial comprehensive psychiatric assessment",
                            "category": "mental_health",
                            "duration_minutes": 60,
                            "base_price": "200.00",
                        },
                        "price_override": "150.00",
                        "effective_price": "150.00",
                        "is_available": True,
                    }
                ],
                "availability": [
                    {
                        "id": 201,
                        "day_of_week": 1,
                        "start_time": "09:00:00",
                        "end_time": "17:00:00",
                        "is_recurring": True,
                        "valid_from": "2024-01-01",
                        "valid_until": None,
                    }
                ],
            },
            response_only=True,
        )
    ]
)
class SpecialistDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for comprehensive specialist profile information.

    Includes nested relationships for services and availability.
    Used in detail views where complete information is required.

    **Fields Description:**

    | Field | Type | Description |
    |-------|------|-------------|
    | id | Integer | Unique identifier for the specialist |
    | user_info | Object | Basic user information (nested) |
    | license_number | String | Professional medical license number |
    | specialization | String | Medical specialization area |
    | qualifications | String | Educational and professional qualifications |
    | years_experience | Integer | Years of professional experience |
    | consultation_fee | Decimal | Initial consultation fee |
    | is_accepting_new_patients | Boolean | Accepting new patients status |
    | bio | String | Detailed professional biography |
    | rating | Decimal | Average patient rating (0.00 - 5.00) |
    | services | Array[Object] | List of services offered (nested) |
    | availability | Array[Object] | Availability schedule (nested) |

    **Notes:**
    - Rating is calculated based on patient reviews
    - Services include both base services and specialist-specific overrides
    - Availability shows recurring schedule patterns
    """

    user_info = serializers.SerializerMethodField(
        help_text="Basic user information including name, email, and phone"
    )
    services = serializers.SerializerMethodField(
        help_text="List of healthcare services offered by this specialist"
    )
    availability = serializers.SerializerMethodField(
        help_text="Recurring availability schedule for appointments"
    )

    class Meta:
        model = Specialist
        fields = [
            "id",
            "user_info",
            "license_number",
            "specialization",
            "qualifications",
            "years_experience",
            "consultation_fee",
            "is_accepting_new_patients",
            "bio",
            "rating",
            "services",
            "availability",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_user_info(self, obj):
        """
        Extract and format basic user information.

        Returns:
            dict: Contains full_name, email, and phone of the specialist
            None: If user doesn't exist
        """
        if obj.user:
            return {
                "full_name": obj.user.get_full_name(),
                "email": obj.user.email,
                "phone": getattr(obj.user, "phone", None),
            }
        return None

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_services(self, obj):
        """
        Get all active services offered by the specialist.

        Returns:
            list: Serialized list of SpecialistService objects

        Notes:
            - Only includes services marked as available
            - Prefetches related service details for performance
        """
        services = obj.services.filter(is_available=True).select_related("service")
        return SpecialistServiceSerializer(services, many=True).data

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_availability(self, obj):
        """
        Get the specialist's recurring availability schedule.

        Returns:
            list: Serialized list of Availability objects

        Notes:
            - Only includes recurring availability entries
            - Non-recurring or one-time availability is excluded
        """
        availability = obj.availability.filter(is_recurring=True)
        return AvailabilitySerializer(availability, many=True).data


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Create Specialist Request",
            description="Example request for creating a new specialist profile",
            value={
                "user_id": 123,
                "email": "dr.jones@example.com",
                "first_name": "John",
                "last_name": "Jones",
                "phone": "+1234567890",
                "license_number": "MD789012",
                "specialization": "therapist",
                "qualifications": "PhD in Clinical Psychology, Licensed Therapist",
                "years_experience": 8,
                "consultation_fee": "120.00",
                "is_accepting_new_patients": True,
                "bio": "Specializing in cognitive behavioral therapy for adults...",
                "rating": "4.5",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Minimal Create Request",
            description="Minimum required fields for specialist creation",
            value={
                "user_id": 124,
                "license_number": "PSY345678",
                "specialization": "psychologist",
                "years_experience": 5,
                "consultation_fee": "100.00",
            },
            request_only=True,
        ),
    ]
)
class SpecialistCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new specialist profiles.

    Handles both specialist profile creation and optional user information updates.

    **Required Fields:**
    - `user_id`: ID of the existing user to associate with specialist profile
    - `license_number`: Professional license number (min 3 characters)
    - `specialization`: Medical specialization
    - `years_experience`: Years of experience (≥ 0)
    - `consultation_fee`: Consultation fee (≥ 0)

    **Optional Fields:**
    - `email`: Update user's email (must be valid email format)
    - `first_name`: Update user's first name
    - `last_name`: Update user's last name
    - `phone`: Update user's phone number
    - `qualifications`: Educational and professional qualifications
    - `is_accepting_new_patients`: New patient acceptance status (default: True)
    - `bio`: Professional biography
    - `rating`: Initial rating (0.00-5.00, optional)

    **Data Validations :**
    1. User must exist and not already have a specialist profile
    2. License number must be at least 3 characters
    3. Years experience cannot be negative
    4. Consultation fee cannot be negative
    5. Rating must be between 0 and 5 (if provided)

    **Permissions:** Admin or staff only
    """

    user_id = serializers.IntegerField(
        required=True,
        help_text="ID of the user account to associate with the specialist profile",
        min_value=1,
    )
    email = serializers.EmailField(
        required=False,
        help_text="Email address for the specialist (updates user email if provided)",
    )
    first_name = serializers.CharField(
        max_length=30,
        required=False,
        help_text="First name of the specialist (updates user first name if provided)",
    )
    last_name = serializers.CharField(
        max_length=30,
        required=False,
        help_text="Last name of the specialist (updates user last name if provided)",
    )
    phone = serializers.CharField(
        max_length=20,
        required=False,
        help_text="Phone number for the specialist (updates user phone if provided)",
    )

    class Meta:
        model = Specialist
        fields = [
            "user_id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "license_number",
            "specialization",
            "qualifications",
            "years_experience",
            "consultation_fee",
            "is_accepting_new_patients",
            "bio",
            "rating",
        ]
        extra_kwargs = {
            "rating": {
                "required": False,
                "help_text": "Initial rating (0.00-5.00). If not provided, defaults to 0.00",
            },
            "qualifications": {
                "required": False,
                "help_text": "Educational and professional qualifications",
            },
            "bio": {
                "required": False,
                "help_text": "Professional biography and background",
            },
            "is_accepting_new_patients": {
                "required": False,
                "help_text": "Whether accepting new patients (default: True)",
            },
        }

    def validate_license_number(self, value):
        """
        Validate license number format.

        Args:
            value (str): License number to validate

        Returns:
            str: Stripped license number

        Raises:
            serializers.ValidationError: If license number is too short

        Business logic validation is performed in the service layer.
        """
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError(
                "License number must be at least 3 characters long"
            )
        return value.strip()

    def validate_years_experience(self, value):
        """
        Validate years of experience.

        Args:
            value (int): Years of experience

        Returns:
            int: Validated years of experience

        Raises:
            serializers.ValidationError: If years experience is negative
        """
        if value < 0:
            raise serializers.ValidationError("Years experience cannot be negative")
        return value

    def validate_consultation_fee(self, value):
        """
        Validate consultation fee.

        Args:
            value (Decimal): Consultation fee amount

        Returns:
            Decimal: Validated consultation fee

        Raises:
            serializers.ValidationError: If fee is negative
        """
        if value < 0:
            raise serializers.ValidationError("Consultation fee cannot be negative")
        return value

    def validate(self, attrs):
        """
        Perform cross-field validation and user existence check.

        Args:
            attrs (dict): All serializer fields

        Returns:
            dict: Validated attributes with added 'user' key

        Raises:
            serializers.ValidationError: If user doesn't exist or already has profile

        Validations:
        1. User must exist in the system
        2. User must not already have a specialist profile
        """
        user_id = attrs.get("user_id")
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError({"user_id": "User not found"})

        # Check if user already has specialist profile
        if hasattr(user, "specialist_profile"):
            raise serializers.ValidationError(
                {"user_id": "User already has a specialist profile"}
            )

        # Store user in validated data for later use in create/update
        attrs["user"] = user

        return attrs


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Update Specialist Request",
            description="Example request for updating specialist profile",
            value={
                "license_number": "MD123457",
                "specialization": "psychiatrist",
                "qualifications": "MD, Board Certified, Updated Certification",
                "years_experience": 11,
                "consultation_fee": "160.00",
                "is_accepting_new_patients": False,
                "bio": "Updated bio with new specialties...",
                "rating": "4.9",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Partial Update Request",
            description="Update only specific fields",
            value={"consultation_fee": "170.00", "is_accepting_new_patients": True},
            request_only=True,
        ),
    ]
)
class SpecialistUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating existing specialist profiles.

    Allows partial updates of specialist information.

    **Updatable Fields:**
    - `license_number`: Professional license number (format validation only)
    - `specialization`: Medical specialization
    - `qualifications`: Educational and professional qualifications
    - `years_experience`: Years of experience (≥ 0)
    - `consultation_fee`: Consultation fee (≥ 0)
    - `is_accepting_new_patients`: New patient acceptance status
    - `bio`: Professional biography
    - `rating`: Patient rating (0.00-5.00)

    **Validation Rules:**
    1. Years experience cannot be negative
    2. Consultation fee cannot be negative
    3. Rating must be between 0 and 5 (inclusive)
    4. License number uniqueness is checked in service layer


    **Note:** Business logic validation (like license uniqueness) is handled
    in the service layer. This serializer only performs format validation.
    """

    class Meta:
        model = Specialist
        fields = [
            "license_number",
            "specialization",
            "qualifications",
            "years_experience",
            "consultation_fee",
            "is_accepting_new_patients",
            "bio",
            "rating",
        ]
        extra_kwargs = {
            "license_number": {
                "help_text": "Professional license number. Uniqueness validated in service layer."
            },
            "qualifications": {
                "required": False,
                "help_text": "Educational and professional qualifications",
            },
            "bio": {
                "required": False,
                "help_text": "Professional biography and background",
            },
            "rating": {
                "required": False,
                "help_text": "Average patient rating (0.00-5.00)",
            },
        }

    def validate_license_number(self, value):
        """
        Basic validation for license number format.

        Args:
            value (str): License number to validate

        Returns:
            str: Validated license number

        Note: Comprehensive uniqueness validation is performed in the service layer.
        """
        instance = self.instance
        # Basic format validation - business logic handled in services
        return value.strip() if value else value

    def validate_years_experience(self, value):
        """
        Validate years of experience is non-negative.

        Args:
            value (int): Years of experience

        Returns:
            int: Validated years of experience

        Raises:
            serializers.ValidationError: If years experience is negative
        """
        if value < 0:
            raise serializers.ValidationError("Years experience cannot be negative")
        return value

    def validate_consultation_fee(self, value):
        """
        Validate consultation fee is non-negative.

        Args:
            value (Decimal): Consultation fee amount

        Returns:
            Decimal: Validated consultation fee

        Raises:
            serializers.ValidationError: If fee is negative
        """
        if value < 0:
            raise serializers.ValidationError("Consultation fee cannot be negative")
        return value

    def validate_rating(self, value):
        """
        Validate rating is within acceptable range (0-5).

        Args:
            value (Decimal): Rating value

        Returns:
            Decimal: Validated rating

        Raises:
            serializers.ValidationError: If rating is outside 0-5 range
        """
        if value < 0:
            raise serializers.ValidationError("Rating cannot be negative")
        if value > 5:
            raise serializers.ValidationError("Rating cannot exceed 5")
        return value


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Search with Filters",
            description="Search specialists with multiple filters",
            value={
                "specialization": "psychiatrist",
                "min_rating": 4.0,
                "max_fee": 200.00,
                "accepting_new_patients": True,
                "service_id": 5,
                "search": "Smith",
                "ordering": "-rating",
                "page": 1,
                "page_size": 20,
            },
            request_only=True,
        ),
        OpenApiExample(
            "Simple Search",
            description="Search with minimal parameters",
            value={"search": "therapist", "page": 1, "page_size": 10},
            request_only=True,
        ),
    ]
)
class SpecialistSearchSerializer(serializers.Serializer):
    """
    Serializer for searching and filtering specialists.

    Used in list endpoints to provide advanced search capabilities.
    All fields are optional - omitting all fields returns all active specialists.

    **Search Parameters:**

    | Parameter | Type | Description | Example |
    |-----------|------|-------------|---------|
    | specialization | String | Filter by medical specialization | `psychiatrist` |
    | min_rating | Decimal | Minimum rating (0.00-5.00) | `4.5` |
    | max_fee | Decimal | Maximum consultation fee | `200.00` |
    | accepting_new_patients | Boolean | Filter by new patient acceptance | `true` |
    | service_id | Integer | Filter by specific service ID | `5` |
    | search | String | Text search in name, email, qualifications, bio | `"Smith therapy"` |
    | ordering | String | Sort order for results | `"-rating"` |
    | page | Integer | Page number (≥ 1) | `1` |
    | page_size | Integer | Items per page (1-100) | `20` |

    **Search Behavior:**
    - Text search (`search` parameter) searches in:
        - First name
        - Last name
        - Email
        - Qualifications
        - Bio
    - Multiple filters are combined with AND logic
    - Empty or null parameters are ignored

    **Ordering Options:**
    - `rating`: Lowest rating first
    - `-rating`: Highest rating first (default)
    - `consultation_fee`: Lowest fee first
    - `-consultation_fee`: Highest fee first
    - `years_experience`: Least experience first
    - `-years_experience`: Most experience first

    **Pagination:**
    - Default: page=1, page_size=20
    - Maximum page_size: 100
    - Returns pagination metadata in response
    """

    specialization = serializers.ChoiceField(
        choices=Specialist.SPECIALIZATION_CHOICES,
        required=False,
        help_text="Filter by medical specialization",
        allow_null=True,
    )
    min_rating = serializers.DecimalField(
        max_digits=3,
        decimal_places=2,
        min_value=0,
        max_value=5,
        required=False,
        help_text="Minimum rating (0.00-5.00). Filters specialists with rating ≥ this value.",
        allow_null=True,
    )
    max_fee = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
        help_text="Maximum consultation fee. Filters specialists with fee ≤ this value.",
        allow_null=True,
    )
    accepting_new_patients = serializers.BooleanField(
        required=False,
        help_text="Filter specialists who are accepting new patients",
        allow_null=True,
    )
    service_id = serializers.IntegerField(
        required=False,
        min_value=1,
        help_text="Filter by specific service ID. Returns specialists offering this service.",
        allow_null=True,
    )
    search = serializers.CharField(
        required=False,
        help_text="""Text search across multiple fields:
        - First name
        - Last name
        - Email
        - Qualifications
        - Bio
        Uses case-insensitive contains search.""",
        allow_blank=True,
        allow_null=True,
    )
    ordering = serializers.ChoiceField(
        choices=[
            "rating",
            "-rating",
            "consultation_fee",
            "-consultation_fee",
            "years_experience",
            "-years_experience",
        ],
        required=False,
        default="rating",
        help_text="Sort order for results. Prefix with '-' for descending order.",
    )
    page = serializers.IntegerField(
        min_value=1,
        required=False,
        default=1,
        help_text="Page number for pagination (1-based)",
    )
    page_size = serializers.IntegerField(
        min_value=1,
        max_value=100,
        required=False,
        default=20,
        help_text="Number of items per page (max: 100)",
    )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Specialist Service",
            description="Service offered by a specialist with pricing",
            value={
                "id": 101,
                "service": 5,
                "service_details": {
                    "id": 5,
                    "name": "Psychiatric Evaluation",
                    "description": "Initial comprehensive psychiatric assessment",
                    "category": "mental_health",
                    "duration_minutes": 60,
                    "base_price": "200.00",
                },
                "price_override": "150.00",
                "effective_price": "150.00",
                "is_available": True,
            },
            response_only=True,
        )
    ]
)
class SpecialistServiceSerializer(serializers.ModelSerializer):
    """
    Serializer for services offered by specialists.

    Represents the relationship between a specialist and a healthcare service,
    including specialist-specific pricing overrides.

    **Fields Description:**

    | Field | Type | Description |
    |-------|------|-------------|
    | id | Integer | Unique identifier for the specialist-service relationship |
    | service | Integer | Foreign key to the Service model |
    | service_details | Object | Detailed information about the service (nested) |
    | price_override | Decimal | Specialist-specific price override (nullable) |
    | effective_price | Decimal | Final price (override if exists, otherwise base price) |
    | is_available | Boolean | Whether this service is currently available |

    **Pricing Logic:**
    - If `price_override` is set, it takes precedence over the service's base price
    - If `price_override` is null, the service's `base_price` is used
    - `effective_price` field provides the final price for consumers

    **Notes:**
    - Services can be temporarily marked as unavailable (`is_available=False`)
    - Price overrides allow specialists to set custom pricing for services
    - Service details include category, duration, and base information
    """

    service_details = ServiceSerializer(
        source="service",
        read_only=True,
        help_text="Detailed information about the healthcare service",
    )
    effective_price = serializers.SerializerMethodField(
        help_text="Final price after applying specialist override"
    )

    class Meta:
        model = SpecialistService
        fields = [
            "id",
            "service",
            "service_details",
            "price_override",
            "effective_price",
            "is_available",
        ]
        read_only_fields = ["id", "service_details", "effective_price"]
        extra_kwargs = {
            "service": {"help_text": "ID of the healthcare service"},
            "price_override": {
                "help_text": "Specialist-specific price override. Null uses service base price.",
                "required": False,
                "allow_null": True,
            },
            "is_available": {
                "help_text": "Whether this service is currently offered by the specialist",
                "default": True,
            },
        }

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_effective_price(self, obj):
        """
        Calculate the effective price for the service.

        Args:
            obj (SpecialistService): The specialist-service relationship instance

        Returns:
            Decimal: The effective price (override if exists, otherwise base price)

        Business Logic:
        1. Check if price_override is set (not null)
        2. If set, return price_override
        3. Otherwise, return service.base_price
        """
        return obj.get_price()


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Add Service Request",
            description="Request to add a service to a specialist",
            value={"service_id": 5, "price_override": "175.50"},
            request_only=True,
        ),
        OpenApiExample(
            "Add Service without Override",
            description="Add service using base price",
            value={"service_id": 8},
            request_only=True,
        ),
    ]
)
class SpecialistServiceCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for adding healthcare services to a specialist's offerings.

    Used when a specialist wants to offer a new service or when
    admin/staff assigns services to specialists.

    **Required Fields:**
    - `service_id`: ID of the service to add (must be positive integer)

    **Optional Fields:**
    - `price_override`: Specialist-specific price for this service

    **Validation Rules:**
    1. Service must exist (validated in service layer)
    2. Service ID must be positive
    3. Price override cannot be negative (if provided)
    4. Specialist cannot already offer this service (handled in service layer)

    **Permissions:**
    - Specialists can add services to their own profile
    - Staff and admins can add services to any specialist

    **Notes:**
    - If price_override is not provided, the service's base_price is used
    - Services are added as available by default
    - Duplicate service additions are prevented by unique constraint
    """

    service_id = serializers.IntegerField(
        required=True,
        help_text="ID of the healthcare service to add to specialist's offerings",
        min_value=1,
    )
    price_override = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
        allow_null=True,
        help_text="Specialist-specific price. If null, uses service's base price.",
    )

    class Meta:
        model = SpecialistService
        fields = ["service_id", "price_override"]

    def validate_service_id(self, value):
        """
        Validate service ID format.

        Args:
            value (int): Service ID to validate

        Returns:
            int: Validated service ID

        Raises:
            serializers.ValidationError: If service ID is not positive

        Note: Service existence validation is performed in the service layer.
        """
        if value <= 0:
            raise serializers.ValidationError("Service ID must be positive")
        return value

    def validate_price_override(self, value):
        """
        Validate price override format.

        Args:
            value (Decimal): Price override to validate

        Returns:
            Decimal: Validated price override

        Raises:
            serializers.ValidationError: If price is negative

        Note: Business logic validation (like price limits) is in service layer.
        """
        if value is not None and value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        return value
