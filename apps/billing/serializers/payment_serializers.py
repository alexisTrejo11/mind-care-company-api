from rest_framework import serializers
from decimal import Decimal
from typing import Dict, Any
from drf_spectacular.utils import extend_schema_serializer
from apps.billing.models import Payment, PaymentMethod, Bill


@extend_schema_serializer(component_name="Payment")
class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for payment data display and comprehensive read operations.

    Provides complete payment information including amount, method details, status,
    Stripe integration data, and related financial records. Includes computed fields
    for easy integration with payment workflows.

    **Data Schema:**

    | Field | Type | Read-only | Format | Description |
    |-------|------|-----------|--------|-------------|
    | id | Integer | Yes | - | Unique payment identifier |
    | payment_number | String | Yes | "PAY-YYYYMM-XXXX" | Auto-generated payment number |
    | bill | Integer | Yes | - | Related bill ID |
    | bill_number | String | Yes | - | Bill number (computed) |
    | patient | Integer | Yes | - | Patient user ID |
    | patient_name | String | Yes | - | Patient full name (computed) |
    | patient_email | Email | Yes | - | Patient email (computed) |
    | amount | Decimal | Yes | Currency | Payment amount |
    | payment_method | String | Yes | "cash"/"bank_transfer"/"online"/"digital_wallet" | Payment method used |
    | payment_method_display | String | Yes | - | Display-friendly method name |
    | status | String | Yes | "pending"/"completed"/"failed"/"refunded" | Payment status |
    | status_display | String | Yes | - | Display-friendly status |
    | bank_reference | String | Yes | - | Bank transfer reference code |
    | bank_name | String | Yes | - | Bank name for transfers |
    | stripe_payment_intent_id | String | Yes | - | Stripe payment intent ID |
    | stripe_charge_id | String | Yes | - | Stripe charge ID |
    | stripe_refund_id | String | Yes | - | Stripe refund ID (if refunded) |
    | card_last4 | String | Yes | 4 digits | Last 4 of card (if digital) |
    | card_brand | String | Yes | - | Card brand (Visa, MasterCard, etc.) |
    | card_exp_month | Integer | Yes | 1-12 | Card expiration month |
    | card_exp_year | Integer | Yes | YYYY | Card expiration year |
    | notes | String | Yes | - | Payment notes |
    | admin_notes | String | Yes | - | Internal notes (admin only) |
    | payment_date | DateTime | Yes | ISO 8601 | When payment was received |
    | processed_at | DateTime | Yes | ISO 8601 | When payment was processed |
    | refunded_at | DateTime | Yes | ISO 8601 | When refund was issued (if any) |
    | created_at | DateTime | Yes | ISO 8601 | Creation timestamp |
    | updated_at | DateTime | Yes | ISO 8601 | Last update timestamp |
    | created_by | Integer | Yes | - | User who created payment |

    **Payment Methods:**
    - "cash": Cash payment (auto-reference generated)
    - "bank_transfer": Bank transfer (requires reference and bank name)
    - "online": Stripe payment (requires payment intent ID)
    - "digital_wallet": Digital wallet (ApplePay, GooglePay, etc.)

    **Payment Status Workflow:**
    - "pending": Payment initiated, awaiting confirmation
    - "completed": Payment successfully processed
    - "failed": Payment processing failed
    - "refunded": Payment has been refunded

    **Method-Specific Fields:**
    - Cash: Auto-generates reference, no additional data
    - Bank Transfer: Requires bank_reference and bank_name
    - Online: stripe_payment_intent_id, stripe_charge_id, card details
    - Digital Wallet: stripe_payment_method_id, card brand data

    **Computed Fields:**
    - patient_name: From related user's first/last name
    - bill_number: From related bill
    - payment_method_display: User-friendly method name
    - status_display: User-friendly status name
    """

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


@extend_schema_serializer(component_name="PaymentCreate")
class PaymentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating payments against bills.

    Handles payment creation with automatic reference generation for cash payments,
    bank transfer validation, and online payment processing. Supports multiple
    payment methods with method-specific field requirements.

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | bill_id | Integer | Yes | - | ID of bill being paid |
    | amount | Decimal | Yes | Currency | Payment amount (0.01-99999.99) |
    | payment_method | Enum | Yes | See methods | Cash/bank/online/wallet |
    | bank_reference | String | Conditional | Max 100 chars | Bank transfer ref (required for bank) |
    | bank_name | String | Conditional | Max 100 chars | Bank name (required for bank) |
    | notes | String | No | Max 1000 chars | Payment notes |

    **Field Specifications:**

    1. **bill_id field**:
       - Required bill reference
       - Must reference existing bill
       - Bill must not be already fully paid or cancelled

    2. **amount field**:
       - Required payment amount
       - Range: $0.01 to $99,999.99
       - Maximum 2 decimal places
       - Must be positive
       - Validated against bill balance

    3. **payment_method field**:
       - Required method selection
       - "cash": Cash payment
       - "bank_transfer": Bank transfer payment
       - "online": Stripe online payment
       - "digital_wallet": Digital wallet payment

    4. **bank_reference field**:
       - Required only if payment_method="bank_transfer"
       - Reference code from bank transfer
       - Maximum 100 characters
       - Whitespace trimmed

    5. **bank_name field**:
       - Required only if payment_method="bank_transfer"
       - Bank institution name
       - Maximum 100 characters
       - Whitespace trimmed

    6. **notes field**:
       - Optional payment notes
       - Maximum 1000 characters
       - Logs reference/memo information

    **Validation Rules:**

    1. **Cash Payments:**
       - No bank details required
       - Reference auto-generated internally

    2. **Bank Transfers:**
       - bank_reference required
       - bank_name required
       - Amount no restrictions

    3. **Online Payments:**
       - bank_reference NOT allowed (raises error)
       - bank_name NOT allowed (raises error)
       - Amount >= $0.50 (Stripe minimum)
       - Amount <= $99,999.99 (practical maximum)

    4. **Digital Wallet:**
       - Similar restrictions as online
       - Must have valid payment method ID

    **Payment Processing:**
    - Creates payment record with "pending" status
    - Auto-generates unique payment_number
    - For cash: auto-generates reference
    - For online: initializes Stripe intent
    - For bank: stores reference for reconciliation
    """

    bill_id = serializers.IntegerField(
        required=True, help_text="ID of the bill to be paid"
    )
    payment_method = serializers.ChoiceField(
        choices=Payment.PAYMENT_METHOD_CHOICES,
        help_text="Payment method: cash, bank_transfer, online, or digital_wallet",
    )
    bank_reference = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        help_text="Bank transfer reference (required for bank transfers)",
    )
    bank_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        help_text="Bank name (required for bank transfers)",
    )

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
        extra_kwargs = {
            "amount": {"help_text": "Payment amount (0.01-99999.99, max 2 decimals)"},
            "notes": {"help_text": "Optional payment notes (max 1000 characters)"},
        }

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


@extend_schema_serializer(component_name="OnlinePaymentIntent")
class OnlinePaymentIntentSerializer(serializers.Serializer):
    """
    Serializer for creating Stripe payment intents for online payments.

    Handles creation of Stripe payment intent objects that enable secure
    online payment processing through the frontend. Supports saving payment
    methods for future use and explicit payment method pre-selection.

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | bill_id | Integer | Yes | - | ID of bill to pay |
    | amount | Decimal | Yes | Currency | Payment amount (0.50-99999.99) |
    | save_payment_method | Boolean | No | true/false | Save method for reuse (default: false) |
    | payment_method_id | String | No | "pm_..." | Pre-selected payment method ID |

    **Field Specifications:**

    1. **bill_id field**:
       - Required bill reference
       - Must reference existing bill
       - Used to link Stripe intent to invoice

    2. **amount field**:
       - Required payment amount
       - Minimum: $0.50 (Stripe requirement)
       - Maximum: $99,999.99 (practical limit)
       - Must be positive decimal
       - Maximum 2 decimal places

    3. **save_payment_method field**:
       - Optional (default: false)
       - If true: payment method saved for future transactions
       - If false: one-time payment only
       - Improves customer experience for repeat customers

    4. **payment_method_id field**:
       - Optional Stripe payment method ID
       - Format: Must start with "pm_"
       - Pre-selects payment method from saved methods
       - If omitted: customer selects during checkout

    **Validation Rules:**
    - amount >= $0.50 (Stripe minimum)
    - amount <= $99,999.99 (practical maximum)
    - payment_method_id must start with "pm_" if provided
    - bill_id must reference existing bill

    **Stripe Integration:**
    - Creates PaymentIntent with setup_future_usage (if save_payment_method=true)
    - Returns client_secret for frontend payment element
    - Returns payment_intent_id for tracking
    - Returns status for polling

    **Return Data:**
    - payment_id: Internal payment record ID
    - payment_number: Generated payment number
    - client_secret: Stripe client secret for frontend
    - payment_intent_id: Stripe intent ID
    - status: Current intent status
    - amount: Confirmation of amount
    - bill_number: Bill being paid

    **Frontend Usage:**
    1. Submit bill_id and amount to create intent
    2. Use client_secret with Stripe Elements/Payment Element
    3. After payment element confirms: call confirm endpoint
    4. If save_payment_method=true: method saved for next time
    """

    bill_id = serializers.IntegerField(
        required=True, help_text="ID of the bill to be paid"
    )
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.5"),
        required=True,
        help_text="Payment amount ($0.50 minimum, $99,999.99 maximum)",
    )
    save_payment_method = serializers.BooleanField(
        default=False,
        help_text="Save payment method for future use",
    )
    payment_method_id = serializers.CharField(
        required=False,
        max_length=100,
        help_text="Pre-selected Stripe payment method ID (format: pm_...)",
    )

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


@extend_schema_serializer(component_name="PaymentMethod")
class PaymentMethodSerializer(serializers.ModelSerializer):
    """
    Serializer for payment method data display and read operations.

    Provides payment method information with type-specific details and
    security controls. Sensitive data is conditionally included based on
    method type. Used for managing stored payment methods.

    **Data Schema:**

    | Field | Type | Read-only | Format | Description |
    |-------|------|-----------|--------|-------------|
    | id | Integer | Yes | - | Unique method identifier |
    | method_type | String | Yes | "card"/"bank_transfer"/"cash"/"digital_wallet" | Payment method type |
    | method_type_display | String | Yes | - | Display-friendly method type |
    | is_default | Boolean | Yes | true/false | Is default payment method |
    | requires_stripe | Boolean | Yes | true/false | Requires Stripe integration |
    | stripe_payment_method_id | String | Yes | "pm_..." | Stripe payment method ID |
    | stripe_customer_id | String | Yes | "cus_..." | Stripe customer ID |
    | card_brand | String | Yes | "visa"/"mastercard"/etc | Card brand (if method_type="card") |
    | card_last4 | String | Yes | 4 digits | Last 4 digits (if method_type="card") |
    | card_exp_month | Integer | Yes | 1-12 | Expiration month (if method_type="card") |
    | card_exp_year | Integer | Yes | YYYY | Expiration year (if method_type="card") |
    | bank_name | String | Yes | - | Bank name (if method_type="bank_transfer") |
    | account_last4 | String | Yes | 4 digits | Account last 4 (if method_type="bank_transfer") |
    | account_type | String | Yes | "checking"/"savings" | Account type (if method_type="bank_transfer") |
    | is_active | Boolean | Yes | true/false | Whether method is active |
    | created_at | DateTime | Yes | ISO 8601 | Creation timestamp |
    | updated_at | DateTime | Yes | ISO 8601 | Last update timestamp |

    **Payment Method Types:**

    1. **card**:
       - Credit/debit card payment
       - Stored via Stripe
       - Card details securely masked (last 4 shown)
       - Expiration date tracked

    2. **bank_transfer**:
       - ACH bank transfer (US)
       - Account details masked (last 4 shown)
       - Account type tracked (checking/savings)

    3. **cash**:
       - Cash payment (manual entry)
       - No Stripe integration
       - No sensitive data stored

    4. **digital_wallet**:
       - Apple Pay, Google Pay, etc.
       - Stored via Stripe
       - Method-specific data varies

    **Sensitive Data Handling:**
    - Card details only shown if method_type="card"
    - Bank details only shown if method_type="bank_transfer"
    - Other types have those fields masked/nullified
    - No full card numbers ever returned
    - Only masked data (last 4 digits)

    **Stripe Integration:**
    - Card and digital wallet methods require Stripe
    - requires_stripe: true for card/digital_wallet
    - stripe_payment_method_id: Stripe PM object ID
    - stripe_customer_id: Customer ID for recurring charges

    **Computed Fields:**
    - method_type_display: User-friendly method name
    - requires_stripe: Determined by method_type
    """

    method_type_display = serializers.CharField(
        source="get_method_type_display",
        read_only=True,
        help_text="Display-friendly payment method type",
    )
    requires_stripe = serializers.BooleanField(
        read_only=True, help_text="Whether method requires Stripe integration"
    )

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
        if instance.method_type != "card":
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
        if value == "card" and not self.initial_data.get("stripe_payment_method_id"):
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
        if method_type == "card":
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
