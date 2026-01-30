# apps/billing/serializers.py
"""
DRF Serializers for billing and payments
"""
from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta

from .models import Bill, BillItem, Payment, Refund, InsuranceClaim, PaymentMethod
from apps.appointments.models import Appointment
from core.responses.api_response import APIResponse

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


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for payments"""

    bill_number = serializers.CharField(source="bill.bill_number", read_only=True)
    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "payment_number",
            "bill",
            "bill_number",
            "patient",
            "patient_name",
            "amount",
            "currency",
            "payment_method",
            "payment_method_display",
            "status",
            "status_display",
            "card_last4",
            "card_brand",
            "stripe_payment_intent_id",
            "stripe_charge_id",
            "is_insurance_payment",
            "insurance_claim_id",
            "notes",
            "error_message",
            "payment_date",
            "processed_at",
            "refunded_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "payment_number",
            "created_at",
            "updated_at",
            "stripe_payment_intent_id",
            "stripe_charge_id",
            "status_display",
            "payment_method_display",
            "payment_date",
            "processed_at",
            "refunded_at",
            "error_message",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value

    def validate(self, attrs):
        """Validate payment"""
        bill = self.instance.bill if self.instance else attrs.get("bill")

        if bill and "amount" in attrs:
            # Check if payment exceeds balance due
            if attrs["amount"] > bill.balance_due:
                raise serializers.ValidationError(
                    {
                        "amount": f"Payment amount cannot exceed balance due (${bill.balance_due})"
                    }
                )

        return attrs


class PaymentCreateSerializer(PaymentSerializer):
    """Serializer for creating payments"""

    bill_id = serializers.IntegerField(write_only=True, required=True)

    class Meta(PaymentSerializer.Meta):
        fields = PaymentSerializer.Meta.fields + ["bill_id"]
        read_only_fields = [
            f
            for f in PaymentSerializer.Meta.read_only_fields
            if f not in ["bill", "bill_number"]
        ]

    def validate_bill_id(self, value):
        """Validate bill"""
        try:
            bill = Bill.objects.get(id=value)

            # Check if bill can be paid
            if bill.payment_status in ["paid", "cancelled", "refunded"]:
                raise serializers.ValidationError(
                    f"Cannot make payment for bill with status: {bill.payment_status}"
                )

            return value

        except Bill.DoesNotExist:
            raise serializers.ValidationError("Bill not found")

    def create(self, validated_data):
        """Create payment"""
        from .services import BillingService

        bill_id = validated_data.pop("bill_id")
        request = self.context.get("request")

        # Create payment using service
        payment = BillingService.create_payment(
            bill_id=bill_id,
            patient=request.user if request else None,
            created_by=request.user if request else None,
            **validated_data,
        )

        return payment


class RefundSerializer(serializers.ModelSerializer):
    """Serializer for refunds"""

    payment_number = serializers.CharField(
        source="payment.payment_number", read_only=True
    )
    bill_number = serializers.CharField(source="bill.bill_number", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)

    class Meta:
        model = Refund
        fields = [
            "id",
            "refund_number",
            "payment",
            "payment_number",
            "bill",
            "bill_number",
            "amount",
            "reason",
            "reason_display",
            "reason_details",
            "status",
            "status_display",
            "stripe_refund_id",
            "requested_date",
            "processed_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "refund_number",
            "created_at",
            "updated_at",
            "status_display",
            "reason_display",
            "requested_date",
            "processed_date",
            "stripe_refund_id",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Refund amount must be greater than 0")
        return value

    def validate(self, attrs):
        """Validate refund"""
        payment = self.instance.payment if self.instance else attrs.get("payment")

        if payment and "amount" in attrs:
            # Check if refund exceeds payment amount
            if attrs["amount"] > payment.amount:
                raise serializers.ValidationError(
                    {
                        "amount": f"Refund amount cannot exceed original payment amount (${payment.amount})"
                    }
                )

            # Check if payment can be refunded
            if payment.status != "completed":
                raise serializers.ValidationError(
                    {"payment": "Only completed payments can be refunded"}
                )

        return attrs


class InsuranceClaimSerializer(serializers.ModelSerializer):
    """Serializer for insurance claims"""

    bill_number = serializers.CharField(source="bill.bill_number", read_only=True)
    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = InsuranceClaim
        fields = [
            "id",
            "claim_number",
            "bill",
            "bill_number",
            "patient",
            "patient_name",
            "insurance_company",
            "policy_number",
            "group_number",
            "subscriber_name",
            "subscriber_relationship",
            "diagnosis_codes",
            "procedure_codes",
            "total_claimed_amount",
            "insurance_responsibility",
            "patient_responsibility",
            "denied_amount",
            "status",
            "status_display",
            "date_of_service",
            "date_submitted",
            "date_acknowledged",
            "date_processed",
            "date_paid",
            "edi_file_name",
            "edi_reference_number",
            "payer_claim_number",
            "notes",
            "denial_reason",
            "appeal_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "claim_number",
            "created_at",
            "updated_at",
            "status_display",
        ]


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for payment methods"""

    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)
    method_type_display = serializers.CharField(
        source="get_method_type_display", read_only=True
    )

    # Masked details for security
    masked_details = serializers.SerializerMethodField()

    class Meta:
        model = PaymentMethod
        fields = [
            "id",
            "patient",
            "patient_name",
            "method_type",
            "method_type_display",
            "is_default",
            "is_active",
            "card_brand",
            "card_last4",
            "card_exp_month",
            "card_exp_year",
            "bank_name",
            "account_last4",
            "account_type",
            "masked_details",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "method_type_display",
            "masked_details",
            "card_brand",
            "card_last4",
            "card_exp_month",
            "card_exp_year",
            "bank_name",
            "account_last4",
            "account_type",
        ]

    def get_masked_details(self, obj) -> str:
        """Get masked payment method details"""
        if obj.card_brand:
            return f"{obj.card_brand} ****{obj.card_last4}"
        elif obj.bank_name:
            return f"{obj.bank_name} ****{obj.account_last4}"
        return "Payment Method"


class CreatePaymentIntentSerializer(serializers.Serializer):
    """Serializer for creating Stripe payment intent"""

    bill_id = serializers.IntegerField(required=True)
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, min_value=0.50
    )
    payment_method_id = serializers.CharField(
        required=False, help_text="Stripe Payment Method ID for saved cards"
    )
    save_payment_method = serializers.BooleanField(default=False)

    def validate(self, attrs):
        """Validate payment intent creation"""
        try:
            bill = Bill.objects.get(id=attrs["bill_id"])

            # Validate bill can be paid
            if bill.payment_status in ["paid", "cancelled", "refunded"]:
                raise serializers.ValidationError(
                    {
                        "bill_id": f"Bill with status {bill.payment_status} cannot be paid"
                    }
                )

            # Set amount to balance due if not specified
            if "amount" not in attrs or not attrs["amount"]:
                attrs["amount"] = bill.balance_due

            # Validate amount
            if attrs["amount"] > bill.balance_due:
                raise serializers.ValidationError(
                    {
                        "amount": f"Amount cannot exceed balance due (${bill.balance_due})"
                    }
                )

            if attrs["amount"] < 0.50:  # Stripe minimum
                raise serializers.ValidationError(
                    {"amount": "Minimum payment amount is $0.50"}
                )

            attrs["bill"] = bill
            return attrs

        except Bill.DoesNotExist:
            raise serializers.ValidationError({"bill_id": "Bill not found"})


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
