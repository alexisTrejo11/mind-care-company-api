from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import Refund


User = get_user_model()


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
