"""
Serializers para especialistas y servicios
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

from .models import Specialist, Service, SpecialistService, Availability
from .validators import (
    validate_license_number,
    validate_consultation_fee,
    validate_service_duration_mins,
    validate_specialization_combo,
)

User = get_user_model()


class ServiceSerializer(serializers.ModelSerializer):
    """Serializer para servicios"""

    effective_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

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
            "effective_price",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_duration_minutes(self, value):
        validate_service_duration_mins(value)
        return value

    def validate_base_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0")
        return value


class SpecialistSerializer(serializers.ModelSerializer):
    """Serializer para especialistas"""

    user_id = serializers.UUIDField(source="user.user_id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)

    class Meta:
        model = Specialist
        fields = [
            "id",
            "user_id",
            "email",
            "full_name",
            "phone",
            "license_number",
            "specialization",
            "qualifications",
            "years_experience",
            "consultation_fee",
            "is_accepting_new_patients",
            "bio",
            "rating",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user_id",
            "email",
            "full_name",
            "phone",
            "rating",
            "created_at",
            "updated_at",
        ]

    def validate_license_number(self, value):
        validate_license_number(value)
        return value.upper()

    def validate_consultation_fee(self, value):
        validate_consultation_fee(value)
        return value

    def validate_years_experience(self, value):
        if value < 0:
            raise serializers.ValidationError("Years of experience cannot be negative")
        if value > 70:
            raise serializers.ValidationError("Please enter a valid number of years")
        return value


class SpecialistDetailSerializer(SpecialistSerializer):
    """Serializer detallado de especialista con servicios"""

    services = ServiceSerializer(many=True, read_only=True, source="service_set")

    class Meta(SpecialistSerializer.Meta):
        fields = SpecialistSerializer.Meta.fields + ["services"]


class SpecialistCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear especialista (requiere usuario existente)"""

    user_id = serializers.UUIDField(write_only=True, required=True)

    class Meta:
        model = Specialist
        fields = [
            "user_id",
            "license_number",
            "specialization",
            "qualifications",
            "years_experience",
            "consultation_fee",
            "is_accepting_new_patients",
            "bio",
        ]

    def validate_user_id(self, value):
        try:
            user = User.objects.get(user_id=value)
            if hasattr(user, "specialist_profile"):
                raise serializers.ValidationError("User is already a specialist")
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")

    def create(self, validated_data):
        user_id = validated_data.pop("user_id")
        user = User.objects.get(user_id=user_id)
        validated_data["user"] = user
        return super().create(validated_data)


class SpecialistServiceSerializer(serializers.ModelSerializer):
    """Serializer para servicios de especialistas"""

    specialist_name = serializers.CharField(
        source="specialist.user.get_full_name", read_only=True
    )
    service_name = serializers.CharField(source="service.name", read_only=True)
    service_category = serializers.CharField(source="service.category", read_only=True)
    service_duration = serializers.IntegerField(
        source="service.duration_minutes", read_only=True
    )
    base_price = serializers.DecimalField(
        source="service.base_price", max_digits=10, decimal_places=2, read_only=True
    )
    effective_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = SpecialistService
        fields = [
            "id",
            "specialist",
            "specialist_name",
            "service",
            "service_name",
            "service_category",
            "service_duration",
            "price_override",
            "base_price",
            "effective_price",
            "is_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        specialist = attrs.get("specialist") or self.instance.specialist
        service = attrs.get("service") or self.instance.service

        # Validar que especialista y servicio sean compatibles
        validate_specialization_combo(specialist.specialization, service.category)

        # Validar precio override
        price_override = attrs.get("price_override")
        if price_override is not None and price_override <= 0:
            raise serializers.ValidationError(
                {"price_override": "Price must be greater than 0"}
            )

        return attrs


class AvailabilitySerializer(serializers.ModelSerializer):
    """Serializer para disponibilidad de especialistas"""

    specialist_name = serializers.CharField(
        source="specialist.user.get_full_name", read_only=True
    )

    class Meta:
        model = Availability
        fields = [
            "id",
            "specialist",
            "specialist_name",
            "day_of_week",
            "start_time",
            "end_time",
            "is_recurring",
            "valid_from",
            "valid_until",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        # Validar tiempos
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")

        if start_time and end_time:
            from .validators import validate_availability_times

            validate_availability_times(start_time, end_time)

        # Validar fechas
        valid_from = attrs.get("valid_from")
        valid_until = attrs.get("valid_until")

        if valid_from:
            from .validators import validate_availability_dates

            validate_availability_dates(valid_from, valid_until)

        # Validar que no se solape con otras disponibilidades
        if self.instance:
            self._validate_availability_overlap(attrs)

        return attrs

    def _validate_availability_overlap(self, attrs):
        """Validar que no haya solapamientos de disponibilidad"""
        specialist = attrs.get("specialist", self.instance.specialist)
        day_of_week = attrs.get("day_of_week", self.instance.day_of_week)
        start_time = attrs.get("start_time", self.instance.start_time)
        end_time = attrs.get("end_time", self.instance.end_time)

        # Buscar disponibilidades solapadas (excluyendo la actual)
        overlapping = Availability.objects.filter(
            specialist=specialist,
            day_of_week=day_of_week,
            start_time__lt=end_time,
            end_time__gt=start_time,
        ).exclude(id=self.instance.id if self.instance else None)

        if overlapping.exists():
            raise serializers.ValidationError(
                "This availability overlaps with existing schedule"
            )


class SpecialistSearchSerializer(serializers.Serializer):
    """Serializer para búsqueda de especialistas"""

    specialization = serializers.ChoiceField(
        choices=Specialist.SPECIALIZATION_CHOICES, required=False
    )
    service_category = serializers.ChoiceField(
        choices=Service.CATEGORY_CHOICES, required=False
    )
    min_experience = serializers.IntegerField(min_value=0, max_value=70, required=False)
    max_fee = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False
    )
    accepting_new_patients = serializers.BooleanField(required=False)
    min_rating = serializers.DecimalField(
        max_digits=3,
        decimal_places=2,
        min_value=Decimal("0.00"),
        max_value=Decimal("5.00"),
        required=False,
    )
    search = serializers.CharField(required=False, max_length=100)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)
