from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from apps.core.exceptions.base_exceptions import NotFoundError
from ..models import Service, SpecialistService


class ServiceSerializer(serializers.ModelSerializer):
    """Serializer for services"""

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

    def validate(self, data):
        # Validate duration
        duration_minutes = data.get("duration_minutes")
        if duration_minutes and duration_minutes < 5:
            raise ValidationError(detail="Minimum service duration is 5 minutes")

        # Validate price
        base_price = data.get("base_price")
        if base_price and base_price < 0:
            raise ValidationError(detail="Base price cannot be negative")

        # Validate name uniqueness within category
        name = data.get("name")
        category = data.get("category")
        if name and category:
            if (
                Service.objects.filter(name=name, category=category)
                .exclude(id=self.instance.id if self.instance else None)
                .exists()
            ):
                raise ValidationError(
                    detail=f"Service with name '{name}' already exists in category '{category}'"
                )

        return data


class ServiceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new services"""

    class Meta:
        model = Service
        fields = [
            "name",
            "description",
            "category",
            "duration_minutes",
            "base_price",
        ]

    def validate_duration_minutes(self, value):
        if value < 5:
            raise ValidationError(detail="Minimum service duration is 5 minutes")
        if value > 480:  # 8 hours
            raise ValidationError(detail="Maximum service duration is 480 minutes")
        return value

    def validate_base_price(self, value):
        if value < 0:
            raise ValidationError(detail="Base price cannot be negative")
        return value


class ServiceUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating services"""

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

    def validate(self, data):
        # If changing name or category, check uniqueness
        instance = self.instance
        if "name" in data or "category" in data:
            name = data.get("name", instance.name)
            category = data.get("category", instance.category)

            if (
                Service.objects.filter(name=name, category=category)
                .exclude(id=instance.id)
                .exists()
            ):
                raise ValidationError(
                    detail=f"Service with name '{name}' already exists in category '{category}'"
                )
        return data


class ServiceSearchSerializer(serializers.Serializer):
    """Serializer for searching services"""

    category = serializers.ChoiceField(choices=Service.CATEGORY_CHOICES, required=False)
    min_duration = serializers.IntegerField(min_value=5, required=False)
    max_duration = serializers.IntegerField(min_value=5, required=False)
    min_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False
    )
    max_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False
    )
    active_only = serializers.BooleanField(default=True)
    search = serializers.CharField(required=False)
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
    )


class ServiceStatsSerializer(serializers.Serializer):
    """Serializer for service statistics"""

    period = serializers.ChoiceField(
        choices=["today", "week", "month", "year", "all_time"], required=True
    )
    include_inactive = serializers.BooleanField(default=False)


class SpecialistServiceCreateSerializer(serializers.ModelSerializer):
    """Serializer for adding services to specialists"""

    service_id = serializers.IntegerField(required=True)
    price_override = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True
    )

    class Meta:
        model = SpecialistService
        fields = ["service_id", "price_override"]

    def validate(self, data):
        request = self.context.get("request")
        specialist_id = self.context.get("specialist_id")

        if not request or not specialist_id:
            return data

        # Verify service exists
        service_id = data.get("service_id")
        try:
            service = Service.objects.get(id=service_id, is_active=True)
        except Service.DoesNotExist:
            raise NotFoundError(detail="Service not found or inactive")

        data["service"] = service

        # Check if specialist already has this service
        if SpecialistService.objects.filter(
            specialist_id=specialist_id, service_id=service_id
        ).exists():
            raise ValidationError(detail="Specialist already offers this service")

        # Verify price_override is reasonable
        price_override = data.get("price_override")
        if price_override and price_override > service.base_price * 3:
            raise ValidationError(
                detail="Price override cannot exceed 3 times the base price"
            )

        return data
