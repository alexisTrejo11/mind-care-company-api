from rest_framework import serializers
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from ..models import Bill, BillItem
from apps.appointments.models import Appointment
from apps.specialists.models import Service
from django.core.exceptions import ValidationError
from apps.core.exceptions.base_exceptions import NotFoundError


class BillItemSerializer(serializers.ModelSerializer):
    """Serializer for reading BillItem data"""

    service_name = serializers.CharField(source="service.name", read_only=True)

    class Meta:
        model = BillItem
        fields = [
            "id",
            "description",
            "quantity",
            "unit_price",
            "tax_rate",
            "discount_rate",
            "line_total",
            "tax_amount",
            "discount_amount",
            "net_amount",
            "service",
            "service_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "line_total",
            "tax_amount",
            "discount_amount",
            "net_amount",
            "service_name",
            "created_at",
            "updated_at",
        ]


class BillItemCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating BillItem"""

    service_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = BillItem
        fields = [
            "description",
            "quantity",
            "unit_price",
            "tax_rate",
            "discount_rate",
            "service_id",
        ]

    def validate_service_id(self, value):
        if value is not None:
            try:
                Service.objects.get(id=value)
            except Service.DoesNotExist:
                raise NotFoundError(detail="Service not found")
        return value

    def validate_quantity(self, value):
        if value <= 0:
            raise ValidationError(message="Quantity must be greater than 0")
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise ValidationError(message="Unit price cannot be negative")
        return value

    def validate_tax_rate(self, value):
        if value < 0 or value > 100:
            raise ValidationError(message="Tax rate must be between 0 and 100")
        return value

    def validate_discount_rate(self, value):
        if value < 0 or value > 100:
            raise ValidationError(message="Discount rate must be between 0 and 100")
        return value


class BillSerializer(serializers.ModelSerializer):
    """Serializer for reading Bill data"""

    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)
    patient_email = serializers.EmailField(source="patient.email", read_only=True)
    appointment_date = serializers.DateTimeField(
        source="appointment.appointment_date", read_only=True
    )
    items = serializers.SerializerMethodField(read_only=True)

    def get_items(self, obj):
        """Get serialized bill items"""
        items = obj.items.all()
        return BillItemSerializer(items, many=True).data

    class Meta:
        model = Bill
        fields = [
            "id",
            "bill_number",
            "patient",
            "patient_name",
            "patient_email",
            "appointment",
            "specialist_name",
            "appointment_type",
            "appointment_date",
            "subtotal",
            "tax_amount",
            "discount_amount",
            "total_amount",
            "amount_paid",
            "balance_due",
            "invoice_status",
            "payment_status",
            "payment_method",
            "insurance_company",
            "policy_number",
            "insurance_coverage",
            "patient_responsibility",
            "invoice_date",
            "due_date",
            "paid_date",
            "notes",
            "stripe_payment_intent_id",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "bill_number",
            "created_at",
            "updated_at",
            "items",
            "patient_name",
            "patient_email",
            "specialist_name",
            "appointment_type",
            "appointment_date",
        ]


class BillCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating bills"""

    appointment_id = serializers.IntegerField(required=True)

    class Meta:
        model = Bill
        fields = [
            "appointment_id",
            "subtotal",
            "tax_amount",
            "discount_amount",
            "total_amount",
            "due_date",
            "insurance_company",
            "policy_number",
            "notes",
        ]

    def validate_appointment_id(self, value):
        try:
            appointment = Appointment.objects.get(id=value)
        except Appointment.DoesNotExist:
            raise NotFoundError(detail="Appointment not found")

        # Check if bill already exists for this appointment
        if hasattr(appointment, "bill"):
            raise ValidationError(message="Bill already exists for this appointment")

        return value

    def validate_due_date(self, value):
        if value <= timezone.now().date():
            raise ValidationError(message="Due date must be in the future")

        # Due date should be within 30 days
        max_due_date = timezone.now().date() + timedelta(days=30)
        if value > max_due_date:
            raise ValidationError(
                message=f"Due date cannot be more than 30 days in the future"
            )

        return value

    def validate(self, data):
        # Validate amount consistency
        subtotal = data.get("subtotal", 0)
        tax_amount = data.get("tax_amount", 0)
        discount_amount = data.get("discount_amount", 0)
        total_amount = data.get("total_amount", 0)

        calculated_total = subtotal + tax_amount - discount_amount

        if abs(total_amount - calculated_total) > 0.01:  # Allow 1 cent tolerance
            raise ValidationError(
                message=f"Total amount ({total_amount}) doesn't match calculation ({calculated_total})"
            )

        # Validate insurance information
        insurance_company = data.get("insurance_company")
        policy_number = data.get("policy_number")

        if (insurance_company and not policy_number) or (
            policy_number and not insurance_company
        ):
            raise ValidationError(
                message="Both insurance company and policy number are required for insurance billing"
            )

        return data


class BillUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating bills"""

    class Meta:
        model = Bill
        fields = [
            "notes",
            "terms_and_conditions",
            "discount_amount",
            "due_date",
        ]

    def validate_due_date(self, value):
        if value <= timezone.now().date():
            raise ValidationError(message="Due date must be in the future")
        return value

    def validate_discount_amount(self, value):
        if value < 0:
            raise ValidationError(message="Discount amount cannot be negative")
        return value


class BillFilterSerializer(serializers.Serializer):
    """Serializer for filtering bills"""

    patient_id = serializers.IntegerField(required=False)
    specialist_id = serializers.IntegerField(required=False)
    appointment_id = serializers.IntegerField(required=False)
    payment_status = serializers.CharField(required=False)
    invoice_status = serializers.CharField(required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    min_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False
    )
    max_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False
    )
    has_insurance = serializers.BooleanField(required=False)
    search = serializers.CharField(required=False, max_length=100)
    ordering = serializers.ChoiceField(
        choices=[
            "invoice_date",
            "-invoice_date",
            "due_date",
            "-due_date",
            "total_amount",
            "-total_amount",
            "balance_due",
            "-balance_due",
        ],
        required=False,
        default="-invoice_date",
    )
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)


class BillingStatsSerializer(serializers.Serializer):
    """Serializer for billing statistics parameters"""

    period = serializers.ChoiceField(
        choices=["today", "week", "month", "year", "all_time"], required=True
    )
    specialist_id = serializers.IntegerField(required=False)
