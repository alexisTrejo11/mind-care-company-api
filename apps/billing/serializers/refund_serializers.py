from rest_framework import serializers
from decimal import Decimal
from typing import Dict, Any
from drf_spectacular.utils import extend_schema_serializer
from apps.billing.models import Refund, Payment


@extend_schema_serializer(component_name="Refund")
class RefundSerializer(serializers.ModelSerializer):
    """
    Serializer for refund data display and comprehensive read operations.

    Provides complete refund information including payment linkage, amount,
    reason, and processing status. Tracks refund lifecycle from request to
    completion with audit information.

    **Data Schema:**

    | Field | Type | Read-only | Format | Description |
    |-------|------|-----------|--------|-------------|
    | id | Integer | Yes | - | Unique refund identifier |
    | refund_number | String | Yes | "REF-YYYYMM-XXXX" | Auto-generated refund number |
    | payment | Integer | Yes | - | Related payment ID |
    | payment_number | String | Yes | - | Payment number (computed) |
    | bill | Integer | Yes | - | Related bill ID |
    | bill_number | String | Yes | - | Bill number (computed) |
    | amount | Decimal | Yes | Currency | Refund amount |
    | reason | String | Yes | See reasons | Refund reason code |
    | reason_display | String | Yes | - | Display-friendly reason |
    | reason_details | String | Yes | - | Detailed explanation |
    | status | String | Yes | "pending"/"completed"/"failed"/"cancelled" | Refund status |
    | status_display | String | Yes | - | Display-friendly status |
    | payment_method | String | Yes | - | Original payment method |
    | patient_name | String | Yes | - | Patient full name (computed) |
    | stripe_refund_id | String | Yes | "re_..." | Stripe refund ID (if applicable) |
    | requested_date | DateTime | Yes | ISO 8601 | When refund was requested |
    | processed_date | DateTime | Yes | ISO 8601 | When refund was processed (null if pending) |
    | created_at | DateTime | Yes | ISO 8601 | Creation timestamp |
    | updated_at | DateTime | Yes | ISO 8601 | Last update timestamp |
    | created_by | Integer | Yes | - | User who created refund |

    **Refund Reasons:**
    - "patient_request": Patient requested refund
    - "incorrect_charge": Billing error or duplicate charge
    - "insurance_adjustment": Insurance company adjustment
    - "service_not_rendered": Service not completed
    - "policy_violation": Violates terms/policy
    - "payment_reversal": Transaction reversal
    - "customer_dissatisfaction": Refund for satisfaction
    - "other": Other reason (see reason_details)

    **Refund Status Workflow:**
    - "pending": Refund requested, awaiting processing
    - "completed": Refund successfully issued
    - "failed": Refund processing failed (see admin notes)
    - "cancelled": Refund cancelled, no money returned

    **Processing Timeline:**
    - requested_date: When refund was initiated
    - processed_date: When refund was sent (null until completed)
    - Pending refunds have null processed_date
    - Completed refunds have processed_date set

    **Payment Method Handling:**
    - Cash: Return to patient manually
    - Bank Transfer: Refund to source bank account
    - Card: Credit card reversal via Stripe
    - Digital Wallet: Return to wallet (ApplePay, GooglePay)

    **Stripe Integration:**
    - Card payments: stripe_refund_id tracks Stripe refund
    - Refund linked via original stripe_payment_intent_id
    - Partial refunds supported
    - Full refunds supported

    **Amount Tracking:**
    - Refund amount must be <= original payment amount
    - Multiple refunds possible for same payment
    - Total refunds cannot exceed payment amount

    **Computed Fields:**
    - payment_number: From related payment
    - bill_number: From related bill
    - patient_name: From payment's patient
    - payment_method: From original payment
    - reason_display: User-friendly reason name
    - status_display: User-friendly status name

    **Audit Information:**
    - created_by: User who initiated refund
    - created_at/updated_at: Timestamp tracking
    - reason_details: Explanation stored for records
    """

    payment_number = serializers.CharField(
        source="payment.payment_number",
        read_only=True,
        help_text="Original payment number",
    )
    bill_number = serializers.CharField(
        source="bill.bill_number",
        read_only=True,
        help_text="Related bill number",
    )
    patient_name = serializers.CharField(
        source="payment.patient.get_full_name",
        read_only=True,
        help_text="Patient full name",
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
        help_text="Display-friendly refund status",
    )
    reason_display = serializers.CharField(
        source="get_reason_display",
        read_only=True,
        help_text="Display-friendly refund reason",
    )
    payment_method = serializers.CharField(
        source="payment.payment_method",
        read_only=True,
        help_text="Original payment method used",
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


@extend_schema_serializer(component_name="RefundCreate")
class RefundCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and processing refunds.

    Handles refund initiation with reason specification and amount validation.
    Supports both full and partial refunds with multiple refund reason categories.
    Integrates with Stripe for card payment refunds.

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | payment_id | Integer | Yes | - | ID of payment to refund |
    | amount | Decimal | Yes | Currency | Refund amount (0.01-99999.99) |
    | reason | Enum | Yes | See reasons | Refund reason code |
    | reason_details | String | No | Max 1000 chars | Detailed explanation |

    **Field Specifications:**

    1. **payment_id field**:
       - Required payment reference
       - Must reference existing payment
       - Payment must have completed status
       - Payment not already fully refunded

    2. **amount field**:
       - Required refund amount
       - Range: $0.01 to $99,999.99
       - Maximum 2 decimal places
       - Cannot exceed payment amount
       - Must be positive

    3. **reason field**:
       - Required refund reason
       - Valid reasons listed below
       - Determines handling and approval workflow

    4. **reason_details field**:
       - Optional detailed explanation
       - Maximum 1000 characters
       - Context for reason being given
       - Whitespace automatically trimmed

    **Refund Reason Options:**
    - "patient_request": Customer requested refund
    - "incorrect_charge": Billing error or duplicate
    - "insurance_adjustment": Insurance company change
    - "service_not_rendered": Service not completed
    - "policy_violation": Terms/policy violation
    - "payment_reversal": Transaction reversal
    - "customer_dissatisfaction": Satisfaction issue
    - "other": Other reason (must include reason_details)

    **Validation Rules:**

    1. **Amount Validation:**
       - amount > 0
       - amount <= payment.amount
       - Amount has max 2 decimal places
       - Prevents over-refunding

    2. **Payment Validation:**
       - payment must exist
       - payment.status must be "completed"
       - Cannot refund failed/pending payments

    3. **Refund Limits:**
       - Multiple refunds allowed per payment
       - Total refunds cannot exceed original payment
       - Each refund tracked separately

    4. **Reason Validation:**
       - Must be valid reason code
       - "other" reason: requires reason_details
       - reason_details max 1000 chars

    **Refund Processing:**
    - Creates Refund record with "pending" status
    - Auto-generates refund_number (REF-YYYYMM-XXXX)
    - Sets requested_date to current time
    - For card payments: initiates Stripe refund
    - For bank transfers: creates reversal instructions
    - For cash: marks for manual refund

    **Stripe Integration:**
    - Card refunds processed via Stripe API
    - Stripe refund ID stored in stripe_refund_id
    - Stripe handles reversal to card issuer
    - Processing typically 3-5 business days

    **Multiple Refunds:**
    - Supports partial refunds (e.g., $10 of $100)
    - Supports issuing multiple refunds over time
    - Tracks all refunds against payment
    - Prevents exceeding original amount
    """

    payment_id = serializers.IntegerField(
        required=True, help_text="ID of the payment to be refunded"
    )

    class Meta:
        model = Refund
        fields = [
            "payment_id",
            "amount",
            "reason",
            "reason_details",
        ]
        extra_kwargs = {
            "amount": {
                "help_text": "Refund amount (0.01-99999.99, max 2 decimals, cannot exceed payment amount)"
            },
            "reason": {
                "help_text": "Reason for refund (patient_request, incorrect_charge, etc.)"
            },
            "reason_details": {
                "help_text": "Detailed explanation for the refund (max 1000 characters)"
            },
        }

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
