from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.db import transaction

from core.exceptions.base_exceptions import NotFoundError
from ..models import Specialist, SpecialistService, Service
from .service_serializers import ServiceSerializer
from .availability_serializers import AvailabilitySerializer


User = get_user_model()


class SpecialistSerializer(serializers.ModelSerializer):
    """Serializer for listing specialists"""

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
    """Serializer for specialist details with related data"""

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
    """Serializer for creating a specialist profile"""

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

    def validate(self, data):
        # Validate user exists and is not already a specialist
        user_id = data.get("user_id")
        try:
            user = User.objects.get(id=user_id)
            if hasattr(user, "specialist_profile"):
                raise DRFValidationError(detail="User already has a specialist profile")
            data["user"] = user
        except User.DoesNotExist:
            raise NotFoundError(detail="User not found")

        # Validate license number uniqueness
        license_number = data.get("license_number")
        if Specialist.objects.filter(license_number=license_number).exists():
            raise DRFValidationError(detail="License number already registered")

        # Validate years_experience
        years_experience = data.get("years_experience", 0)
        if years_experience < 0:
            raise DRFValidationError(detail="Years experience cannot be negative")

        # Validate consultation_fee
        consultation_fee = data.get("consultation_fee", 0)
        if consultation_fee < 0:
            raise DRFValidationError(detail="Consultation fee cannot be negative")

        # Update user info if provided
        if data.get("email"):
            validate_email(data["email"])
            user.email = data["email"]

        if data.get("first_name"):
            user.first_name = data["first_name"]

        if data.get("last_name"):
            user.last_name = data["last_name"]

        if data.get("phone"):
            user.phone = data["phone"]

        return data

    @transaction.atomic
    def create(self, validated_data):
        # Extract user update data
        user_data = {}
        for field in ["email", "first_name", "last_name", "phone"]:
            if field in validated_data:
                user_data[field] = validated_data.pop(field)

        # Update user if needed
        user = validated_data.pop("user")
        if user_data:
            for key, value in user_data.items():
                setattr(user, key, value)
            user.save()

        # Remove user_id from validated_data
        validated_data.pop("user_id", None)

        # Create specialist
        specialist = Specialist.objects.create(user=user, **validated_data)
        return specialist


class SpecialistUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating specialist profile"""

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
        instance = self.instance
        if (
            Specialist.objects.filter(license_number=value)
            .exclude(id=instance.id)
            .exists()
        ):
            raise DRFValidationError(detail="License number already registered")
        return value

    def validate(self, data):
        # Validate years_experience
        if "years_experience" in data and data["years_experience"] < 0:
            raise DRFValidationError(detail="Years experience cannot be negative")

        # Validate consultation_fee
        if "consultation_fee" in data and data["consultation_fee"] < 0:
            raise DRFValidationError(detail="Consultation fee cannot be negative")

        return data


class SpecialistSearchSerializer(serializers.Serializer):
    """Serializer for searching specialists"""

    specialization = serializers.CharField(required=False)
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
    """Serializer for specialist services"""

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
            raise DRFValidationError(detail="Specialist already offers this service")

        # Verify price_override is reasonable
        price_override = data.get("price_override")
        if price_override and price_override > service.base_price * 3:
            raise DRFValidationError(
                detail="Price override cannot exceed 3 times the base price"
            )

        return data
