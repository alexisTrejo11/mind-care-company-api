from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.db import transaction

from apps.core.exceptions.base_exceptions import NotFoundError
from ..models import Specialist, SpecialistService, Service
from .service_serializers import ServiceSerializer
from .availability_serializers import AvailabilitySerializer


User = get_user_model()


class SpecialistSerializer(serializers.ModelSerializer):
    """Serializer for listing specialists - DATA FORMAT ONLY"""

    specialist_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    service_count = serializers.SerializerMethodField()

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

    def get_specialist_name(self, obj):
        return obj.user.get_full_name() if obj.user else None

    def get_email(self, obj):
        return obj.user.email if obj.user else None

    def get_phone(self, obj):
        return getattr(obj.user, "phone", None) if obj.user else None

    def get_service_count(self, obj):
        return obj.services.filter(is_available=True).count()


class SpecialistDetailSerializer(serializers.ModelSerializer):
    """Serializer for specialist details - DATA FORMAT ONLY"""

    user_info = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()
    availability = serializers.SerializerMethodField()

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

    def get_user_info(self, obj):
        if obj.user:
            return {
                "full_name": obj.user.get_full_name(),
                "email": obj.user.email,
                "phone": getattr(obj.user, "phone", None),
            }
        return None

    def get_services(self, obj):
        services = obj.services.filter(is_available=True).select_related("service")
        return SpecialistServiceSerializer(services, many=True).data

    def get_availability(self, obj):
        availability = obj.availability.filter(is_recurring=True)
        return AvailabilitySerializer(availability, many=True).data


class SpecialistCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a specialist profile - DATA FORMAT ONLY"""

    user_id = serializers.IntegerField(required=True)
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(max_length=30, required=False)
    last_name = serializers.CharField(max_length=30, required=False)
    phone = serializers.CharField(max_length=20, required=False)

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
            "rating": {"required": False},
        }

    def validate_license_number(self, value):
        """Format validation only - business logic in services"""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError(
                "License number must be at least 3 characters long"
            )
        return value.strip()

    def validate_years_experience(self, value):
        """Format validation only - business logic in services"""
        if value < 0:
            raise serializers.ValidationError("Years experience cannot be negative")
        return value

    def validate_consultation_fee(self, value):
        """Format validation only - business logic in services"""
        if value < 0:
            raise serializers.ValidationError("Consultation fee cannot be negative")
        return value

    def validate(self, attrs):
        """Check basic data consistency - business logic in services"""
        # Check if user exists
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

        # Store user in validated data for later use
        attrs["user"] = user

        return attrs


class SpecialistUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating specialist profile - DATA FORMAT ONLY"""

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

    def validate_license_number(self, value):
        """Basic uniqueness check - business logic in services"""
        instance = self.instance
        # This is a basic check; comprehensive validation is in services
        return value

    def validate_years_experience(self, value):
        """Format validation only - business logic in services"""
        if value < 0:
            raise serializers.ValidationError("Years experience cannot be negative")
        return value

    def validate_consultation_fee(self, value):
        """Format validation only - business logic in services"""
        if value < 0:
            raise serializers.ValidationError("Consultation fee cannot be negative")
        return value

    def validate_rating(self, value):
        """Format validation only - business logic in services"""
        if value < 0:
            raise serializers.ValidationError("Rating cannot be negative")
        if value > 5:
            raise serializers.ValidationError("Rating cannot exceed 5")
        return value


class SpecialistSearchSerializer(serializers.Serializer):
    """Serializer for searching specialists - DATA FORMAT ONLY"""

    specialization = serializers.ChoiceField(
        choices=Specialist.SPECIALIZATION_CHOICES, required=False
    )
    min_rating = serializers.DecimalField(
        max_digits=3, decimal_places=2, min_value=0, max_value=5, required=False
    )
    max_fee = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False
    )
    accepting_new_patients = serializers.BooleanField(required=False)
    service_id = serializers.IntegerField(required=False)
    search = serializers.CharField(required=False)
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
    )
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(
        min_value=1, max_value=100, required=False, default=20
    )


class SpecialistServiceSerializer(serializers.ModelSerializer):
    """Serializer for specialist services - DATA FORMAT ONLY"""

    service_details = ServiceSerializer(source="service", read_only=True)
    effective_price = serializers.SerializerMethodField()

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

    def get_effective_price(self, obj):
        return obj.get_price()


class SpecialistServiceCreateSerializer(serializers.ModelSerializer):
    """Serializer for adding services to specialists - DATA FORMAT ONLY"""

    service_id = serializers.IntegerField(required=True)
    price_override = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True
    )

    class Meta:
        model = SpecialistService
        fields = ["service_id", "price_override"]

    def validate_service_id(self, value):
        """Basic format validation - business logic in services"""
        if value <= 0:
            raise serializers.ValidationError("Service ID must be positive")
        return value

    def validate_price_override(self, value):
        """Basic format validation - business logic in services"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        return value
