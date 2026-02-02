from rest_framework import serializers
from billing.models import Payment, Bill, PaymentMethod
from apps.core.exceptions.base_exceptions import NotFoundError
from rest_framework.exceptions import ValidationError


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for reading payment data"""

    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)
    bill_number = serializers.CharField(source="bill.bill_number", read_only=True)

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
            "payment_method",
            "currency",
            "status",
            "card_last4",
            "card_brand",
            "is_insurance_payment",
            "insurance_claim_id",
            "notes",
            "payment_date",
            "processed_at",
            "stripe_payment_intent_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payments"""

    bill_id = serializers.IntegerField(required=True)

    class Meta:
        model = Payment
        fields = [
            "bill_id",
            "amount",
            "payment_method",
            "notes",
            "is_insurance_payment",
            "insurance_claim_id",
        ]

    def validate_bill_id(self, value):
        try:
            bill = Bill.objects.get(id=value)
        except Bill.DoesNotExist:
            raise NotFoundError(detail="Bill not found")

        # Check if bill can accept payments
        if bill.payment_status in ["paid", "cancelled", "refunded"]:
            raise ValidationError(
                detail=f"Cannot make payment for bill with status: {bill.payment_status}"
            )

        return value

    def validate_amount(self, value):
        if value <= 0:
            raise ValidationError(detail="Payment amount must be greater than 0")
        return value

    def validate(self, data):
        bill_id = data.get("bill_id")
        amount = data.get("amount")

        if bill_id and amount:
            try:
                bill = Bill.objects.get(id=bill_id)
                if amount > bill.balance_due:
                    raise ValidationError(
                        detail=f"Payment amount (${amount}) exceeds balance due (${bill.balance_due})"
                    )
            except Bill.DoesNotExist:
                pass

        # Validate insurance payment
        is_insurance_payment = data.get("is_insurance_payment", False)
        insurance_claim_id = data.get("insurance_claim_id")

        if is_insurance_payment and not insurance_claim_id:
            raise ValidationError(
                detail="Insurance claim ID is required for insurance payments"
            )


class CreatePaymentIntentSerializer(serializers.Serializer):
    """Serializer for creating Stripe payment intents"""

    bill_id = serializers.IntegerField(required=True)
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0.5, required=True
    )

    def validate_bill_id(self, value):
        try:
            bill = Bill.objects.get(id=value)
        except Bill.DoesNotExist:
            raise NotFoundError(detail="Bill not found")

        # Check if bill can accept online payments
        if bill.payment_status in ["paid", "cancelled", "refunded"]:
            raise ValidationError(
                detail=f"Cannot make payment for bill with status: {bill.payment_status}"
            )

        if bill.balance_due <= 0:
            raise ValidationError(detail="Bill has no balance due")

        return value

    def validate_amount(self, value):
        if value < 0.5:  # Stripe minimum
            raise ValidationError(detail="Minimum payment amount is $0.50")
        return value

    def validate(self, data):
        bill_id = data.get("bill_id")
        amount = data.get("amount")

        if bill_id and amount:
            try:
                bill = Bill.objects.get(id=bill_id)
                if amount > bill.balance_due:
                    raise ValidationError(
                        detail=f"Payment amount (${amount}) exceeds balance due (${bill.balance_due})"
                    )
            except Bill.DoesNotExist:
                pass

        return data

        return data


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for reading payment method data"""

    class Meta:
        model = PaymentMethod
        fields = [
            "id",
            "method_type",
            "is_default",
            "card_brand",
            "card_last4",
            "card_exp_month",
            "card_exp_year",
            "bank_name",
            "account_last4",
            "account_type",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
