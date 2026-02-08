from rest_framework import serializers
from decimal import Decimal
from typing import Dict, Any
from apps.billing.models import Payment, PaymentMethod, Bill
from apps.core.exceptions.base_exceptions import NotFoundError
from apps.users.models import User


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for reading payment data"""

    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)
    bill_number = serializers.CharField(source="bill.bill_number", read_only=True)
    patient_email = serializers.EmailField(source="patient.email", read_only=True)
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
            "patient_email",
            "amount",
            "payment_method",
            "payment_method_display",
            "status",
            "status_display",
            "bank_reference",
            "bank_name",
            "stripe_payment_intent_id",
            "stripe_charge_id",
            "stripe_refund_id",
            "card_last4",
            "card_brand",
            "card_exp_month",
            "card_exp_year",
            "notes",
            "admin_notes",
            "error_message",
            "payment_date",
            "processed_at",
            "refunded_at",
            "created_at",
            "updated_at",
            "created_by",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "bill": {"read_only": True},
            "patient": {"read_only": True},
            "created_by": {"read_only": True},
        }


class PaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payments"""

    bill_id = serializers.IntegerField(required=True)
    payment_method = serializers.ChoiceField(choices=Payment.PAYMENT_METHOD_CHOICES)
    bank_reference = serializers.CharField(
        required=False, allow_blank=True, max_length=100
    )
    bank_name = serializers.CharField(required=False, allow_blank=True, max_length=100)

    class Meta:
        model = Payment
        fields = [
            "bill_id",
            "amount",
            "payment_method",
            "bank_reference",
            "bank_name",
            "notes",
        ]

    def validate_bill_id(self, value: int) -> int:
        """Validate bill ID exists"""
        if not Bill.objects.filter(id=value).exists():
            raise serializers.ValidationError("Bill not found")
        return value

    def validate_amount(self, value: Decimal) -> Decimal:
        """Validate amount format and value"""
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be greater than 0")

        # Validate decimal places
        exponent = value.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -2:  # More than 2 decimal places
            raise serializers.ValidationError(
                "Amount can have maximum 2 decimal places"
            )

        return value

    def validate_bank_reference(self, value: str) -> str:
        """Validate bank reference"""
        if value and len(value) > 100:
            raise serializers.ValidationError(
                "Bank reference cannot exceed 100 characters"
            )
        return value.strip() if value else value

    def validate_bank_name(self, value: str) -> str:
        """Validate bank name"""
        if value and len(value) > 100:
            raise serializers.ValidationError("Bank name cannot exceed 100 characters")
        return value.strip() if value else value

    def validate_notes(self, value: str) -> str:
        """Validate notes"""
        if value and len(value) > 1000:
            raise serializers.ValidationError("Notes cannot exceed 1000 characters")
        return value.strip() if value else value

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate payment method specific requirements"""
        payment_method = data.get("payment_method")

        # Validate bank transfer requires reference
        if payment_method == "bank_transfer":
            if not data.get("bank_reference"):
                raise serializers.ValidationError(
                    {"bank_reference": "Bank reference is required for bank transfers"}
                )
            if not data.get("bank_name"):
                raise serializers.ValidationError(
                    {"bank_name": "Bank name is required for bank transfers"}
                )

        # For cash payments, we can auto-generate reference
        elif payment_method == "cash":
            data["bank_reference"] = f"CASH-TEMP-REF"  # Will be replaced in service

        # For online payments, don't allow bank reference
        elif payment_method == "online":
            if data.get("bank_reference") or data.get("bank_name"):
                raise serializers.ValidationError(
                    {
                        "bank_reference": "Bank reference should not be provided for online payments"
                    }
                )

        return data


class OnlinePaymentIntentSerializer(serializers.Serializer):
    """Serializer for creating Stripe payment intents"""

    bill_id = serializers.IntegerField(required=True)
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.5"), required=True
    )
    save_payment_method = serializers.BooleanField(default=False)
    payment_method_id = serializers.CharField(required=False, max_length=100)

    def validate_bill_id(self, value: int) -> int:
        """Validate bill ID exists"""
        if not Bill.objects.filter(id=value).exists():
            raise serializers.ValidationError("Bill not found")
        return value

    def validate_amount(self, value: Decimal) -> Decimal:
        """Validate amount for online payments"""
        if value < Decimal("0.5"):  # Stripe minimum
            raise serializers.ValidationError("Minimum payment amount is $0.50")

        if value > Decimal("99999.99"):  # Reasonable maximum
            raise serializers.ValidationError("Maximum payment amount is $99,999.99")

        return value

    def validate_payment_method_id(self, value: str) -> str:
        """Validate Stripe payment method ID format"""
        if value and not value.startswith("pm_"):
            raise serializers.ValidationError("Invalid payment method ID format")
        return value


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for payment method data"""

    method_type_display = serializers.CharField(
        source="get_method_type_display", read_only=True
    )
    requires_stripe = serializers.BooleanField(read_only=True)

    class Meta:
        model = PaymentMethod
        fields = [
            "id",
            "method_type",
            "method_type_display",
            "is_default",
            "requires_stripe",
            "stripe_payment_method_id",
            "stripe_customer_id",
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

    def to_representation(self, instance: PaymentMethod) -> Dict[str, Any]:
        """Custom representation to hide sensitive data"""
        data = super().to_representation(instance)

        # Only show card details if method type is digital payment
        if instance.method_type != "digital payment":
            data["card_brand"] = None
            data["card_last4"] = None
            data["card_exp_month"] = None
            data["card_exp_year"] = None

        # Only show bank details if method type is bank transfer
        if instance.method_type != "bank_transfer":
            data["bank_name"] = None
            data["account_last4"] = None
            data["account_type"] = None

        return data


class PaymentMethodCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payment methods"""

    method_type = serializers.ChoiceField(
        choices=PaymentMethod.PAYMENT_METHOD_TYPE_CHOICES
    )
    stripe_payment_method_id = serializers.CharField(required=False, max_length=100)

    class Meta:
        model = PaymentMethod
        fields = [
            "method_type",
            "stripe_payment_method_id",
            "card_brand",
            "card_last4",
            "card_exp_month",
            "card_exp_year",
            "bank_name",
            "account_last4",
            "account_type",
            "is_default",
        ]

    def validate_method_type(self, value: str) -> str:
        """Validate method type"""
        if value == "digital payment" and not self.initial_data.get(
            "stripe_payment_method_id"
        ):
            raise serializers.ValidationError(
                "Stripe payment method ID is required for digital payments"
            )
        return value

    def validate_stripe_payment_method_id(self, value: str) -> str:
        """Validate Stripe payment method ID"""
        if value and not value.startswith("pm_"):
            raise serializers.ValidationError("Invalid Stripe payment method ID format")
        return value

    def validate_card_last4(self, value: str) -> str:
        """Validate card last 4 digits"""
        if value and (len(value) != 4 or not value.isdigit()):
            raise serializers.ValidationError("Card last 4 must be 4 digits")
        return value

    def validate_card_exp_month(self, value: int) -> int:
        """Validate card expiration month"""
        if value and (value < 1 or value > 12):
            raise serializers.ValidationError(
                "Expiration month must be between 1 and 12"
            )
        return value

    def validate_card_exp_year(self, value: int) -> int:
        """Validate card expiration year"""
        if value and value < 2024:  # Adjust based on current year
            raise serializers.ValidationError(
                "Expiration year must be current or future year"
            )
        return value

    def validate_account_last4(self, value: str) -> str:
        """Validate account last 4 digits"""
        if value and (len(value) != 4 or not value.isdigit()):
            raise serializers.ValidationError("Account last 4 must be 4 digits")
        return value

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate consistency of payment method data"""
        method_type = data.get("method_type")

        # Digital payment validations
        if method_type == "digital payment":
            required_card_fields = [
                "card_brand",
                "card_last4",
                "card_exp_month",
                "card_exp_year",
            ]
            missing_fields = [
                field for field in required_card_fields if not data.get(field)
            ]

            if missing_fields:
                raise serializers.ValidationError(
                    {
                        "card_fields": f"For digital payments, these fields are required: {', '.join(missing_fields)}"
                    }
                )

            # Don't allow bank fields for digital payments
            bank_fields = ["bank_name", "account_last4", "account_type"]
            for field in bank_fields:
                if data.get(field):
                    raise serializers.ValidationError(
                        {field: f"Cannot provide {field} for digital payments"}
                    )

        # Bank transfer validations
        elif method_type == "bank_transfer":
            required_bank_fields = ["bank_name", "account_last4"]
            missing_fields = [
                field for field in required_bank_fields if not data.get(field)
            ]

            if missing_fields:
                raise serializers.ValidationError(
                    {
                        "bank_fields": f"For bank transfers, these fields are required: {', '.join(missing_fields)}"
                    }
                )

            # Don't allow card fields for bank transfers
            card_fields = [
                "card_brand",
                "card_last4",
                "card_exp_month",
                "card_exp_year",
            ]
            for field in card_fields:
                if data.get(field):
                    raise serializers.ValidationError(
                        {field: f"Cannot provide {field} for bank transfers"}
                    )

        # Cash validations
        elif method_type == "cash":
            # Don't allow any payment method specific fields for cash
            disallowed_fields = [
                "stripe_payment_method_id",
                "card_brand",
                "card_last4",
                "card_exp_month",
                "card_exp_year",
                "bank_name",
                "account_last4",
                "account_type",
            ]

            for field in disallowed_fields:
                if data.get(field):
                    raise serializers.ValidationError(
                        {field: f"Cannot provide {field} for cash payments"}
                    )

        return data
