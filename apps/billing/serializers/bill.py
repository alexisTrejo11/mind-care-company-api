from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..models import Bill, BillItem
from apps.appointments.models import Appointment

User = get_user_model()


class BillItemSerializer(serializers.ModelSerializer):
    """Serializer for bill items"""

    net_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

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
            "created_at",
        ]
        read_only_fields = [
            "id",
            "line_total",
            "tax_amount",
            "discount_amount",
            "net_amount",
            "created_at",
        ]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative")
        return value


class BillSerializer(serializers.ModelSerializer):
    """Base serializer for bills"""

    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)
    patient_email = serializers.EmailField(source="patient.email", read_only=True)
    patient_phone = serializers.CharField(source="patient.phone", read_only=True)

    appointment_date = serializers.DateTimeField(
        source="appointment.appointment_date", read_only=True
    )
    specialist_name = serializers.CharField(
        source="appointment.specialist.user.get_full_name", read_only=True
    )

    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )
    invoice_status_display = serializers.CharField(
        source="get_invoice_status_display", read_only=True
    )
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )

    items = BillItemSerializer(many=True, read_only=True)
    items_total = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True, source="calculate_items_total"
    )

    days_overdue = serializers.SerializerMethodField()
    can_pay_online = serializers.SerializerMethodField()
    payment_url = serializers.SerializerMethodField()

    class Meta:
        model = Bill
        fields = [
            "id",
            "bill_number",
            "appointment",
            "appointment_date",
            "patient",
            "patient_name",
            "patient_email",
            "patient_phone",
            "specialist_name",
            # Financial
            "subtotal",
            "tax_amount",
            "discount_amount",
            "total_amount",
            "amount_paid",
            "balance_due",
            # Status
            "invoice_status",
            "invoice_status_display",
            "payment_status",
            "payment_status_display",
            "payment_method",
            "payment_method_display",
            # Insurance
            "insurance_company",
            "policy_number",
            "insurance_claim_id",
            "insurance_coverage",
            "patient_responsibility",
            # Dates
            "invoice_date",
            "due_date",
            "paid_date",
            "days_overdue",
            # Items
            "items",
            "items_total",
            # Payment
            "can_pay_online",
            "payment_url",
            # Stripe
            "stripe_payment_intent_id",
            # Notes
            "notes",
            "terms_and_conditions",
            # Metadata
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "bill_number",
            "created_at",
            "updated_at",
            "subtotal",
            "tax_amount",
            "discount_amount",
            "total_amount",
            "amount_paid",
            "balance_due",
            "patient_responsibility",
            "invoice_date",
            "payment_status_display",
            "invoice_status_display",
            "payment_method_display",
            "days_overdue",
            "can_pay_online",
            "payment_url",
            "items_total",
        ]

    def get_days_overdue(self, obj) -> int:
        """Calculate days overdue"""
        if obj.payment_status == "overdue":
            return (timezone.now().date() - obj.due_date).days
        return 0

    def get_can_pay_online(self, obj) -> bool:
        """Check if bill can be paid online"""
        return (
            obj.payment_status in ["pending", "partial", "overdue"]
            and obj.balance_due > 0
        )

    def get_payment_url(self, obj) -> str:
        """Get payment URL"""
        return obj.get_payment_url() if self.get_can_pay_online(obj) else ""

    def validate_due_date(self, value):
        """Validate due date"""
        if value < timezone.now().date():
            raise serializers.ValidationError("Due date cannot be in the past")
        return value

    def validate(self, attrs):
        """Cross-field validation"""
        # Ensure due date is after invoice date
        if "due_date" in attrs:
            invoice_date = (
                self.instance.invoice_date if self.instance else timezone.now().date()
            )
            if attrs["due_date"] <= invoice_date:
                raise serializers.ValidationError(
                    {"due_date": "Due date must be after invoice date"}
                )

        return attrs


class BillCreateSerializer(BillSerializer):
    """Serializer for creating bills"""

    appointment_id = serializers.IntegerField(write_only=True, required=True)

    class Meta(BillSerializer.Meta):
        fields = BillSerializer.Meta.fields + ["appointment_id"]
        read_only_fields = [
            f
            for f in BillSerializer.Meta.read_only_fields
            if f not in ["appointment", "appointment_date"]
        ]

    def validate_appointment_id(self, value):
        """Validate appointment"""
        try:
            appointment = Appointment.objects.get(id=value)

            # Check if appointment is completed
            if appointment.status != "completed":
                raise serializers.ValidationError(
                    "Bills can only be created for completed appointments"
                )

            # Check if bill already exists
            if hasattr(appointment, "bill"):
                raise serializers.ValidationError(
                    "Bill already exists for this appointment"
                )

            return value

        except Appointment.DoesNotExist:
            raise serializers.ValidationError("Appointment not found")

    def create(self, validated_data):
        """Create bill with items"""
        from .services import BillingService

        appointment_id = validated_data.pop("appointment_id")

        # Create bill using service
        bill = BillingService.create_bill_from_appointment(
            appointment_id=appointment_id,
            created_by=self.context["request"].user,
            **validated_data,
        )

        return bill


class BillUpdateSerializer(BillSerializer):
    """Serializer for updating bills (limited fields)"""

    class Meta(BillSerializer.Meta):
        read_only_fields = BillSerializer.Meta.read_only_fields + [
            "appointment",
            "patient",
            "bill_number",
            "subtotal",
            "tax_amount",
            "discount_amount",
            "total_amount",
            "insurance_company",
            "policy_number",
        ]


class BillingStatsSerializer(serializers.Serializer):
    """Serializer for billing statistics"""

    period = serializers.ChoiceField(
        choices=["today", "week", "month", "quarter", "year"], default="month"
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    specialist_id = serializers.IntegerField(required=False)


class BillFilterSerializer(serializers.Serializer):
    """Serializer for filtering bills"""

    patient_id = serializers.UUIDField(required=False)
    specialist_id = serializers.IntegerField(required=False)
    payment_status = serializers.ChoiceField(
        choices=Bill.PAYMENT_STATUS_CHOICES, required=False
    )
    invoice_status = serializers.ChoiceField(
        choices=Bill.INVOICE_STATUS_CHOICES, required=False
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    min_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False
    )
    max_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False
    )
    has_insurance = serializers.BooleanField(required=False)
    search = serializers.CharField(required=False, max_length=100)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)
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
