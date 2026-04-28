from rest_framework import serializers
from drf_spectacular.utils import (
    extend_schema_serializer,
    OpenApiExample,
)

from decimal import Decimal

from apps.core.exceptions.base_exceptions import NotFoundError
from ..models import Service, SpecialistService
from rest_framework.exceptions import ValidationError


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Service Example",
            description="Healthcare service with mental health category",
            value={
                "id": 1,
                "name": "Psychiatric Evaluation",
                "description": "Initial comprehensive psychiatric assessment including diagnosis and treatment planning",
                "category": "mental_health",
                "duration_minutes": 60,
                "base_price": "200.00",
                "is_active": True,
            },
            response_only=True,
        ),
        OpenApiExample(
            "General Medicine Service",
            description="General healthcare service",
            value={
                "id": 2,
                "name": "General Checkup",
                "description": "Routine health examination and consultation",
                "category": "general_medicine",
                "duration_minutes": 30,
                "base_price": "80.00",
                "is_active": True,
            },
            response_only=True,
        ),
    ]
)
class ServiceSerializer(serializers.ModelSerializer):
    """
    Serializer for healthcare service listings and basic service information.

    Represents healthcare services offered by the facility that can be assigned
    to specialists. Services define the type, duration, and base pricing for
    healthcare consultations and procedures.

    **Fields Description:**

    | Field | Type | Description | Constraints |
    |-------|------|-------------|-------------|
    | id | Integer | Unique service identifier | Read-only |
    | name | String | Service name | 1-100 characters |
    | description | String | Detailed service description | Optional |
    | category | String | Service category | From CATEGORY_CHOICES |
    | duration_minutes | Integer | Appointment duration in minutes | ≥ 5 minutes |
    | base_price | Decimal | Standard price for this service | ≥ 0 |
    | is_active | Boolean | Whether service is available | Default: True |

    **Category Choices:**

    - `mental_health`: Mental health services (therapy, counseling, psychiatry)
    - `general_medicine`: General medical services (checkups, consultations)
    - `specialist_consultation`: Specialist medical consultations
    - `diagnostic`: Diagnostic tests and procedures
    - `therapy`: Physical or occupational therapy
    - `wellness`: Wellness and preventive care services

    **Notes:**
    - Base price serves as default; specialists can override with custom pricing
    - Inactive services are hidden from public listings but remain in system
    - Duration is in minutes and affects appointment scheduling
    """

    class Meta:
        model = Service
        fields = [
            "id",
            "name",
            "description",
            "category",
            "duration_minutes",
            "base_price",
            "is_active",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "name": {
                "help_text": "Name of the healthcare service (e.g., 'Psychiatric Evaluation')",
                "min_length": 1,
                "max_length": 100,
            },
            "description": {
                "help_text": "Detailed description of what the service includes",
                "required": False,
                "allow_blank": True,
            },
            "category": {"help_text": "Category grouping for this service"},
            "duration_minutes": {
                "help_text": "Standard duration of this service in minutes (minimum: 5)",
                "min_value": 5,
            },
            "base_price": {
                "help_text": "Standard price for this service before any specialist overrides",
                "min_value": 0,
            },
            "is_active": {
                "help_text": "Whether this service is available for assignment to specialists",
                "default": True,
            },
        }


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Create Service Request",
            description="Create a new therapy service",
            value={
                "name": "Cognitive Behavioral Therapy",
                "description": "Structured psychotherapy that focuses on challenging and changing cognitive distortions",
                "category": "therapy",
                "duration_minutes": 50,
                "base_price": "120.00",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Create Diagnostic Service",
            description="Create a diagnostic service",
            value={
                "name": "Blood Test Panel",
                "description": "Comprehensive blood analysis including CBC, lipid panel, and metabolic panel",
                "category": "diagnostic",
                "duration_minutes": 15,
                "base_price": "75.00",
            },
            request_only=True,
        ),
    ]
)
class ServiceCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new healthcare services.

    Used by administrators to add new service offerings to the platform.
    All created services are active by default.

    **Required Fields:**
    - `name`: Service name (must be unique within its category)
    - `category`: Service category (from CATEGORY_CHOICES)
    - `duration_minutes`: Duration in minutes (≥ 5)
    - `base_price`: Standard price (≥ 0)

    **Optional Fields:**
    - `description`: Detailed service description

    **Validation Rules:**
    1. Name must be unique within the category
    2. Duration must be at least 5 minutes
    3. Base price cannot be negative
    4. Category must be valid choice

    """

    class Meta:
        model = Service
        fields = [
            "name",
            "description",
            "category",
            "duration_minutes",
            "base_price",
        ]
        extra_kwargs = {
            "name": {
                "help_text": "Unique name for the service within its category",
                "min_length": 1,
                "max_length": 100,
            },
            "description": {
                "help_text": "What patients can expect from this service",
                "required": False,
                "allow_blank": True,
            },
            "duration_minutes": {
                "help_text": "Standard appointment duration in minutes (minimum 5)",
                "min_value": 5,
            },
            "base_price": {
                "help_text": "Standard price for this service (minimum 0)",
                "min_value": 0,
            },
        }

    def validate_duration_minutes(self, value):
        """
        Validate service duration is positive.

        Args:
            value (int): Duration in minutes

        Returns:
            int: Validated duration

        Raises:
            ValidationError: If duration is zero or negative

        Business Rules:
        - Minimum duration: 5 minutes
        - Standard durations: 15, 30, 45, 60 minutes (multiples of 15 recommended)
        """
        if value <= 0:
            raise ValidationError(detail="Service duration must be greater than zero")
        if value < 5:
            raise ValidationError(detail="Minimum service duration is 5 minutes")
        if value > 480:  # 8 hours
            raise ValidationError(
                detail="Service duration cannot exceed 480 minutes (8 hours)"
            )
        if value % 15 != 0:
            raise ValidationError(
                detail="Service duration should ideally be a multiple of 15   minutes"
            )
        return value

    def validate_base_price(self, value):
        """
        Validate base price is non-negative.

        Args:
            value (Decimal): Service base price

        Returns:
            Decimal: Validated base price

        Raises:
            ValidationError: If price is negative

        Business Rules:
        - Base price represents the standard rate
        - Specialists can override this price for their offerings
        - Price should reflect service complexity and duration
        """
        if value < 0:
            raise ValidationError(detail="Base price cannot be negative")
        return value


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Update Service Request",
            description="Update service information",
            value={
                "name": "Extended Psychiatric Evaluation",
                "description": "Updated: 90-minute comprehensive assessment including family history",
                "category": "mental_health",
                "duration_minutes": 90,
                "base_price": "250.00",
                "is_active": True,
            },
            request_only=True,
        ),
        OpenApiExample(
            "Deactivate Service",
            description="Mark service as inactive",
            value={"is_active": False},
            request_only=True,
        ),
    ]
)
class ServiceUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating existing healthcare services.

    Allows partial updates of service information including activation/deactivation.

    **Updatable Fields:**
    - `name`: Service name (requires uniqueness check)
    - `description`: Service description
    - `category`: Service category (requires uniqueness check)
    - `duration_minutes`: Duration in minutes (≥ 5)
    - `base_price`: Standard price (≥ 0)
    - `is_active`: Activation status

    **Validation Rules:**
    1. Name must remain unique within category
    2. If changing name or category, new combination must be unique
    3. Duration must be at least 5 minutes
    4. Base price cannot be negative

    **Special Considerations:**
    - Deactivating a service (`is_active=False`):
        - Removes from public listings
        - Prevents new assignments to specialists
        - Existing specialist offerings remain active
    - Reactivating restores availability

    """

    class Meta:
        model = Service
        fields = [
            "name",
            "description",
            "category",
            "duration_minutes",
            "base_price",
            "is_active",
        ]
        extra_kwargs = {
            "name": {
                "help_text": "Service name (must be unique within category)",
                "required": False,
                "min_length": 1,
                "max_length": 100,
            },
            "description": {
                "help_text": "Updated service description",
                "required": False,
                "allow_blank": True,
            },
            "duration_minutes": {
                "help_text": "Updated duration in minutes",
                "required": False,
                "min_value": 5,
            },
            "base_price": {
                "help_text": "Updated standard price",
                "required": False,
                "min_value": 0,
            },
            "is_active": {
                "help_text": "Activation status. False hides from new assignments.",
                "required": False,
            },
        }

    def validate(self, data):
        """
        Perform cross-field validation for service updates.

        Args:
            data (dict): Update data

        Returns:
            dict: Validated data

        Raises:
            ValidationError: If name/category combination already exists

        Validations:
        1. Ensure (name, category) combination remains unique
        2. Only check uniqueness if name or category is being changed
        3. Exclude current instance from uniqueness check
        """
        instance = self.instance

        # Check if we're changing name or category
        name_changed = "name" in data and data["name"] != instance.name
        category_changed = "category" in data and data["category"] != instance.category

        if name_changed or category_changed:
            # Get the values to check
            name = data.get("name", instance.name)
            category = data.get("category", instance.category)

            # Check if another service has this name/category combination
            if (
                Service.objects.filter(name=name, category=category)
                .exclude(id=instance.id)
                .exists()
            ):
                raise ValidationError(
                    detail=f"Service with name '{name}' already exists in category '{category}'"
                )

        return data


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Advanced Service Search",
            description="Search services with multiple filters",
            value={
                "category": "mental_health",
                "min_duration": 30,
                "max_duration": 90,
                "min_price": 50.00,
                "max_price": 200.00,
                "active_only": True,
                "search": "therapy",
                "ordering": "base_price",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Simple Category Filter",
            description="Filter by category only",
            value={"category": "wellness", "active_only": True},
            request_only=True,
        ),
        OpenApiExample(
            "Price Range Search",
            description="Find affordable services",
            value={"max_price": 100.00, "ordering": "duration_minutes"},
            request_only=True,
        ),
    ]
)
class ServiceSearchSerializer(serializers.Serializer):
    """
    Serializer for searching and filtering healthcare services.

    Provides advanced filtering capabilities for service listings.
    All parameters are optional - empty search returns all services
    (subject to active_only default).

    **Search Parameters:**

    | Parameter | Type | Description | Default | Example |
    |-----------|------|-------------|---------|---------|
    | category | String | Filter by service category | None | `mental_health` |
    | min_duration | Integer | Minimum duration (minutes) | None | `30` |
    | max_duration | Integer | Maximum duration (minutes) | None | `90` |
    | min_price | Decimal | Minimum base price | None | `50.00` |
    | max_price | Decimal | Maximum base price | None | `200.00` |
    | active_only | Boolean | Show only active services | `True` | `false` |
    | search | String | Text search in name/description | None | `"therapy"` |
    | ordering | String | Sort order for results | `name` | `"-base_price"` |

    **Search Behavior:**
    - Text search (`search` parameter) searches in:
        - Service name (case-insensitive contains)
        - Service description (case-insensitive contains)
    - Duration filters: `min_duration ≤ duration ≤ max_duration`
    - Price filters: `min_price ≤ price ≤ max_price`
    - Multiple filters combine with AND logic
    - Empty/null parameters are ignored

    **Ordering Options:**
    - `name`: Alphabetical A-Z
    - `-name`: Alphabetical Z-A
    - `duration_minutes`: Shortest duration first
    - `-duration_minutes`: Longest duration first
    - `base_price`: Lowest price first
    - `-base_price`: Highest price first
    - `category`: By category name A-Z
    - `-category`: By category name Z-A

    **Common Use Cases:**
    1. Find mental health services under $150:
       ```json
       {"category": "mental_health", "max_price": 150.00}
       ```
    2. Search for quick consultations:
       ```json
       {"max_duration": 30, "ordering": "duration_minutes"}
       ```
    3. Browse all wellness services:
       ```json
       {"category": "wellness", "active_only": true}
       ```
    """

    category = serializers.ChoiceField(
        choices=Service.CATEGORY_CHOICES,
        required=False,
        help_text="Filter by service category",
        allow_null=True,
    )
    min_duration = serializers.IntegerField(
        min_value=1,
        required=False,
        help_text="Minimum service duration in minutes",
        allow_null=True,
    )
    max_duration = serializers.IntegerField(
        min_value=1,
        required=False,
        help_text="Maximum service duration in minutes",
        allow_null=True,
    )
    min_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
        help_text="Minimum base price",
        allow_null=True,
    )
    max_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
        help_text="Maximum base price",
        allow_null=True,
    )
    active_only = serializers.BooleanField(
        default=True,
        help_text="Include only active services. Set to false to include inactive.",
    )
    search = serializers.CharField(
        required=False,
        help_text="""Text search across:
        - Service name (contains, case-insensitive)
        - Service description (contains, case-insensitive)""",
        allow_blank=True,
        allow_null=True,
    )
    ordering = serializers.ChoiceField(
        choices=[
            "name",
            "-name",
            "duration_minutes",
            "-duration_minutes",
            "base_price",
            "-base_price",
            "category",
            "-category",
        ],
        required=False,
        default="name",
        help_text="Sort order for results. Prefix with '-' for descending.",
    )

    def validate(self, data):
        """
        Validate search parameter combinations.

        Args:
            data (dict): Search parameters

        Returns:
            dict: Validated search parameters

        Raises:
            ValidationError: If min > max for duration or price

        Validations:
        1. Ensure min_duration ≤ max_duration when both provided
        2. Ensure min_price ≤ max_price when both provided
        """
        min_duration = data.get("min_duration")
        max_duration = data.get("max_duration")
        min_price = data.get("min_price")
        max_price = data.get("max_price")

        # Validate duration range
        if min_duration and max_duration and min_duration > max_duration:
            raise ValidationError(
                detail="min_duration cannot be greater than max_duration"
            )

        # Validate price range
        if min_price and max_price and min_price > max_price:
            raise ValidationError(detail="min_price cannot be greater than max_price")

        return data


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Monthly Statistics",
            description="Get service statistics for current month",
            value={"period": "month", "include_inactive": False},
            request_only=True,
        ),
        OpenApiExample(
            "All-time Statistics",
            description="Get comprehensive statistics including inactive",
            value={"period": "all_time", "include_inactive": True},
            request_only=True,
        ),
    ]
)
class ServiceStatsSerializer(serializers.Serializer):
    """
    Serializer for retrieving service usage and performance statistics.

    Provides analytics on service popularity, usage patterns, and performance metrics.
    Used by administrators for business intelligence and service optimization.

    **Required Fields:**
    - `period`: Time period for statistics aggregation

    **Optional Fields:**
    - `include_inactive`: Whether to include inactive services in statistics

    **Period Options:**

    | Period | Description | Typical Use |
    |--------|-------------|-------------|
    | `today` | Statistics for current day | Daily performance monitoring |
    | `week` | Statistics for current week | Weekly trend analysis |
    | `month` | Statistics for current month | Monthly performance review |
    | `year` | Statistics for current year | Annual planning |
    | `all_time` | All historical data | Long-term trend analysis |

    **Business Intelligence Applications:**
    1. Identify popular services for resource allocation
    2. Track revenue by service category
    3. Monitor service utilization rates
    4. Identify underperforming services

    **Permissions:** Admin or staff only

    **Performance Notes:**
    - Statistics are calculated on-demand
    - Large time periods may have slower response times
    - Consider caching for frequently accessed statistics
    """

    period = serializers.ChoiceField(
        choices=["today", "week", "month", "year", "all_time"],
        required=True,
        help_text="Time period for statistics aggregation",
    )
    include_inactive = serializers.BooleanField(
        default=False, help_text="Include inactive services in statistics calculation"
    )

    def validate_period(self, value):
        """
        Validate period parameter.

        Args:
            value (str): Period selection

        Returns:
            str: Validated period

        Notes:
        - "today": Data from 00:00:00 to 23:59:59 current local time
        - "week": Monday 00:00:00 to Sunday 23:59:59 current week
        - "month": 1st 00:00:00 to last day 23:59:59 current month
        - "year": Jan 1 00:00:00 to Dec 31 23:59:59 current year
        - "all_time": All available historical data
        """
        return value


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Add Service with Override",
            description="Add service with custom pricing",
            value={"service_id": 5, "price_override": 175.50},
            request_only=True,
        ),
        OpenApiExample(
            "Add Service Base Price",
            description="Add service using standard pricing",
            value={"service_id": 8},
            request_only=True,
        ),
    ]
)
class SpecialistServiceCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for adding healthcare services to a specialist's offerings.

    Creates the many-to-many relationship between specialists and services
    with optional specialist-specific pricing.

    **Required Fields:**
    - `service_id`: ID of the service to add (must be active)

    **Optional Fields:**
    - `price_override`: Custom price for this specialist (null = use base price)

    **Validation Rules:**
    1. Service must exist and be active
    2. Specialist must not already offer this service
    3. Price override cannot be negative
    4. Price override cannot exceed 3x base price (business rule)

    **Context Requirements:**
    This serializer requires context with:
    - `request`: HTTP request object (for user permissions)
    - `specialist_id`: ID of the specialist (from URL or request)

    **Permissions:**
    - Specialists can add services to their own profile
    - Staff/admins can add services to any specialist

    **Business Logic:**
    - Services added are available by default (`is_available=True`)
    - Price override allows specialists to set custom rates
    - 3x price cap prevents excessive pricing
    - Unique constraint prevents duplicate service assignments

    **Example Successful Response:**
    ```json
    {
        "id": 101,
        "specialist": 25,
        "service": 5,
        "price_override": "175.50",
        "effective_price": "175.50",
        "is_available": true
    }
    ```

    **Error Scenarios:**
    1. Service not found: `{"detail": "Service not found or inactive"}`
    2. Already offers service: `{"detail": "Specialist already offers this service"}`
    3. Price too high: `{"detail": "Price override cannot exceed 3 times the base price"}`
    """

    service_id = serializers.IntegerField(
        required=True,
        help_text="ID of the service to add to specialist's offerings",
        min_value=1,
    )
    price_override = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
        allow_null=True,
        help_text="Specialist-specific price. If null, uses service's base price. Max: 3x base price.",
    )

    class Meta:
        model = SpecialistService
        fields = ["service_id", "price_override"]

    def validate(self, data):
        """
        Comprehensive validation for service assignment.

        Args:
            data (dict): Serializer data

        Returns:
            dict: Validated data with additional 'service' key

        Raises:
            NotFoundError: If service doesn't exist or is inactive
            ValidationError: For business rule violations

        Validations:
        1. Service existence and activity status
        2. No duplicate service assignments
        3. Reasonable price override limits
        """
        request = self.context.get("request")
        specialist_id = self.context.get("specialist_id")

        if not request or not specialist_id:
            return data

        service_id = data.get("service_id")
        try:
            service = Service.objects.get(id=service_id, is_active=True)
        except Service.DoesNotExist:
            raise NotFoundError(detail="Service not found or inactive")

        data["service"] = service

        if SpecialistService.objects.filter(
            specialist_id=specialist_id, service_id=service_id
        ).exists():
            raise ValidationError(detail="Specialist already offers this service")

        price_override = data.get("price_override")
        if price_override:
            base_price = service.base_price
            max_allowed = base_price * 3

            if price_override > max_allowed:
                raise ValidationError(
                    detail=f"Price override cannot exceed 3 times the base price (${max_allowed})"
                )

            min_allowed = base_price * Decimal("0.5")
            if price_override < min_allowed:
                raise ValidationError(
                    detail=f"Price override cannot be less than 50% of base price (${min_allowed})"
                )

        return data
