from rest_framework import serializers
from decimal import Decimal
from typing import Dict, Any
from apps.billing.models import Refund, Payment


class RefundSerializer(serializers.ModelSerializer):
    """Serializer for refunds"""

    payment_number = serializers.CharField(
        source="payment.payment_number", read_only=True
    )
    bill_number = serializers.CharField(source="bill.bill_number", read_only=True)
    patient_name = serializers.CharField(
        source="payment.patient.get_full_name", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    payment_method = serializers.CharField(
        source="payment.payment_method", read_only=True
    )

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
            "payment_method",
            "patient_name",
            "stripe_refund_id",
            "requested_date",
            "processed_date",
            "created_at",
            "updated_at",
            "created_by",
        ]
        read_only_fields = [
            "id",
            "refund_number",
            "status_display",
            "reason_display",
            "requested_date",
            "processed_date",
            "stripe_refund_id",
            "created_at",
            "updated_at",
            "created_by",
        ]

    def validate_amount(self, value: Decimal) -> Decimal:
        """Validate refund amount"""
        if value <= 0:
            raise serializers.ValidationError("Refund amount must be greater than 0")

        # Validate decimal places
        if value.as_tuple().exponent < -2:  # More than 2 decimal places
            raise serializers.ValidationError(
                "Amount can have maximum 2 decimal places"
            )

        return value

    def validate_reason(self, value: str) -> str:
        """Validate refund reason"""
        valid_reasons = [choice[0] for choice in Refund.REFUND_REASON_CHOICES]
        if value not in valid_reasons:
            raise serializers.ValidationError(
                f"Invalid refund reason. Must be one of: {', '.join(valid_reasons)}"
            )
        return value

    def validate_reason_details(self, value: str) -> str:
        """Validate reason details"""
        if value and len(value) > 1000:
            raise serializers.ValidationError(
                "Reason details cannot exceed 1000 characters"
            )
        return value.strip() if value else value


class RefundCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating refunds"""

    payment_id = serializers.IntegerField(required=True)

    class Meta:
        model = Refund
        fields = [
            "payment_id",
            "amount",
            "reason",
            "reason_details",
        ]

    def validate_payment_id(self, value: int) -> int:
        """Validate payment ID exists"""
        if not Payment.objects.filter(id=value).exists():
            raise serializers.ValidationError("Payment not found")
        return value

    def validate_amount(self, value: Decimal) -> Decimal:
        """Validate refund amount format"""
        if value <= 0:
            raise serializers.ValidationError("Refund amount must be greater than 0")

        if value.as_tuple().exponent < -2:  # More than 2 decimal places
            raise serializers.ValidationError(
                "Amount can have maximum 2 decimal places"
            )

        return value

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate refund consistency"""
        # Additional validations that require payment object
        # Note: Business logic like "can this payment be refunded?" should be in service
        return data
