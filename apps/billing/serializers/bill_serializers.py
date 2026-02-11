from rest_framework import serializers
from decimal import Decimal
from typing import Dict, Any
from drf_spectacular.utils import extend_schema_serializer
from apps.billing.models import Bill, BillItem
from apps.appointments.models import Appointment
from apps.users.models import User


@extend_schema_serializer(component_name="BillItem")
class BillItemSerializer(serializers.ModelSerializer):
    """
    Serializer for bill line items display and read operations.

    Provides detailed information about individual bill line items with
    auto-calculated amounts, taxes, and discounts. Used for viewing invoice details.

    **Data Schema:**

    | Field | Type | Read-only | Format | Description |
    |-------|------|-----------|--------|-------------|
    | id | Integer | Yes | - | Unique line item identifier |
    | description | String | Yes | - | Service or item description |
    | quantity | Decimal | Yes | 0.01-10000.00 | Number of units |
    | unit_price | Decimal | Yes | Currency | Price per unit |
    | tax_rate | Decimal | Yes | 0-100% | Tax percentage |
    | discount_rate | Decimal | Yes | 0-100% | Discount percentage |
    | line_total | Decimal | Yes | Currency | Quantity × unit_price |
    | tax_amount | Decimal | Yes | Currency | Calculated tax |
    | discount_amount | Decimal | Yes | Currency | Calculated discount |
    | net_amount | Decimal | Yes | Currency | Final amount (line_total - discount + tax) |
    | service | String | Yes | - | Service type identifier |
    | created_at | DateTime | Yes | ISO 8601 | Creation timestamp |
    | updated_at | DateTime | Yes | ISO 8601 | Last update timestamp |

    **Field Specifications:**

    1. **Item Details**:
       - description: Service or item name
       - quantity: Number of units (supports decimals)
       - unit_price: Price per unit
       - service: Service category code

    2. **Financial Calculations** (auto-calculated):
       - line_total = quantity × unit_price
       - discount_amount = line_total × (discount_rate / 100)
       - tax_amount = (line_total - discount_amount) × (tax_rate / 100)
       - net_amount = line_total - discount_amount + tax_amount

    3. **Tax & Discount**:
       - tax_rate: Applied after discount (as percentage 0-100)
       - discount_rate: Applied before tax (as percentage 0-100)
       - Both applied automatically on save

    4. **Metadata**:
       - created_at/updated_at: Automatic timestamp tracking

    **Currency Format:** All monetary amounts are Decimal(10,2) for precision
    """

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
            "updated_at",
        ]
        read_only_fields = fields


@extend_schema_serializer(component_name="Bill")
class BillSerializer(serializers.ModelSerializer):
    """
    Serializer for bill data display and comprehensive read operations.

    Provides complete invoice information including patient details, appointment info,
    financial summary, insurance details, and itemized list. Used for viewing bills
    and generating invoices. All computed fields are calculated from related records.

    **Data Schema:**

    | Field | Type | Read-only | Format | Description |
    |-------|------|-----------|--------|-------------|
    | id | Integer | Yes | - | Unique bill identifier |
    | bill_number | String | Yes | "BILL-YYYYMM-XXXX" | Auto-generated bill number |
    | appointment | Integer | Yes | - | Related appointment ID |
    | patient | Integer | Yes | - | Patient user ID |
    | patient_name | String | Yes | - | Computed patient full name |
    | patient_email | Email | Yes | - | Computed patient email |
    | specialist_name | String | Yes | - | Computed specialist full name |
    | appointment_type | String | Yes | "consultation"/"therapy"/"follow_up"/"emergency" | Appointment type |
    | subtotal | Decimal | Yes | Currency | Sum of line items before tax |
    | tax_amount | Decimal | Yes | Currency | Total tax across items |
    | discount_amount | Decimal | Yes | Currency | Total discount across items |
    | total_amount | Decimal | Yes | Currency | Final bill amount |
    | amount_paid | Decimal | Yes | Currency | Sum of completed payments |
    | balance_due | Decimal | Yes | Currency | total_amount - amount_paid |
    | invoice_status | String | Yes | "draft"/"sent"/"viewed"/"overdue"/"paid"/"cancelled" | Invoice status |
    | payment_status | String | Yes | "pending"/"partial"/"paid"/"overdue"/"cancelled" | Payment status |
    | insurance_company | String | Yes | - | Insurance provider name |
    | policy_number | String | Yes | - | Insurance policy number |
    | insurance_coverage | Decimal | Yes | Currency | Insurance coverage amount |
    | invoice_date | DateTime | Yes | ISO 8601 | Date invoice was created |
    | due_date | DateTime | Yes | ISO 8601 | Payment due date |
    | paid_date | DateTime | Yes | ISO 8601 | Date fully paid (null if pending) |
    | cancellation_date | DateTime | Yes | ISO 8601 | Date cancelled (null if active) |
    | notes | String | Yes | - | Bill notes and remarks |
    | terms_and_conditions | String | Yes | - | Payment terms |
    | items | Array | Yes | BillItemSerializer | Line items array |
    | payment_count | Integer | Yes | - | Number of payments |
    | created_at | DateTime | Yes | ISO 8601 | Creation timestamp |
    | updated_at | DateTime | Yes | ISO 8601 | Last update timestamp |
    | created_by | Integer | Yes | - | User who created bill |

    **Computed Fields:**
    - amount_paid: Sum of all completed payments for this bill
    - balance_due: Calculated as total_amount - amount_paid
    - payment_status: Determined by payment_count and due_date ("pending", "partial", "paid", "overdue", "cancelled")
    - patient_name: Derived from patient user's first and last name
    - specialist_name: Derived from related appointment's specialist
    - appointment_type: Display value from appointment

    **Invoice Status Workflow:**
    - "draft": Initial state, not yet sent
    - "sent": Sent to patient
    - "viewed": Patient has viewed
    - "overdue": Past due date with unpaid balance
    - "paid": Fully paid
    - "cancelled": Cancelled with no payment due

    **Payment Status Options:**
    - "pending": No payments received
    - "partial": Some payments received, balance remaining
    - "paid": Fully paid
    - "overdue": Past due date with remaining balance
    - "cancelled": Bill cancelled

    **Insurance Information:**
    - Optional insurance company and policy details
    - insurance_coverage: Amount covered by insurance
    - Supports tracking insurance claims separately
    """

    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)
    patient_email = serializers.EmailField(source="patient.email", read_only=True)
    specialist_name = serializers.CharField(
        source="appointment.specialist.user.get_full_name", read_only=True
    )
    appointment_type = serializers.CharField(
        source="appointment.get_appointment_type_display", read_only=True
    )
    invoice_status_display = serializers.CharField(
        source="get_invoice_status_display", read_only=True
    )
    amount_paid = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    balance_due = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    payment_status = serializers.CharField(read_only=True)
    items = BillItemSerializer(many=True, read_only=True)
    payment_count = serializers.IntegerField(source="payments.count", read_only=True)

    class Meta:
        model = Bill
        fields = [
            "id",
            "bill_number",
            "appointment",
            "patient",
            "patient_name",
            "patient_email",
            "specialist_name",
            "appointment_type",
            "subtotal",
            "tax_amount",
            "discount_amount",
            "total_amount",
            "amount_paid",
            "balance_due",
            "invoice_status",
            "invoice_status_display",
            "payment_status",
            "insurance_company",
            "policy_number",
            "insurance_coverage",
            "invoice_date",
            "due_date",
            "paid_date",
            "cancellation_date",
            "notes",
            "terms_and_conditions",
            "stripe_invoice_id",
            "stripe_customer_id",
            "items",
            "payment_count",
            "created_at",
            "updated_at",
            "created_by",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "appointment": {"read_only": True},
            "patient": {"read_only": True},
            "created_by": {"read_only": True},
        }


@extend_schema_serializer(component_name="BillCreate")
class BillCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new bills from appointments.

    Handles bill creation with appointment assignment, insurance information,
    and payment terms. Automatically calculates bill amounts from appointment
    and line item services. Bill number is auto-generated on creation.

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | appointment_id | Integer | Yes | - | ID of the appointment |
    | insurance_company | String | No | Max 100 chars | Insurance provider name |
    | policy_number | String | No | Max 50 chars | Insurance policy number |
    | insurance_coverage | Decimal | No | Currency | Coverage amount |
    | due_date | DateTime | Yes | ISO 8601 | Payment due date |
    | notes | String | No | - | Additional billing notes |
    | terms_and_conditions | String | No | - | Payment terms |

    **Field Specifications:**

    1. **appointment_id field**:
       - Required appointment reference
       - Must reference existing appointment
       - Patient and specialist auto-linked from appointment
       - Bill items auto-created from appointment services

    2. **insurance_company field**:
       - Optional insurance provider name
       - Maximum 100 characters
       - Whitespace automatically trimmed

    3. **policy_number field**:
       - Optional insurance policy number
       - Maximum 50 characters
       - Whitespace automatically trimmed

    4. **insurance_coverage field**:
       - Optional coverage amount in currency
       - Limited to 2 decimal places
       - Must be non-negative

    5. **due_date field**:
       - Required payment due date
       - Must be on or after invoice date
       - ISO 8601 format with timezone

    6. **notes and terms_and_conditions fields**:
       - Optional text fields for documentation
       - Support full invoice customization
       - included in generated invoices

    **Bill Creation Process:**
    1. Validates appointment exists and is not already billed
    2. Auto-links patient and specialist from appointment
    3. Auto-creates bill items from appointment services
    4. Calculates subtotal, tax, discount from items
    5. Generates unique bill number (BILL-YYYYMM-XXXX)
    6. Sets invoice_status as "draft"
    7. Initializes payment_status as "pending"
    """

    appointment_id = serializers.IntegerField(
        required=True, help_text="ID of the appointment to bill"
    )

    class Meta:
        model = Bill
        fields = [
            "appointment_id",
            "insurance_company",
            "policy_number",
            "insurance_coverage",
            "due_date",
            "notes",
            "terms_and_conditions",
        ]
        extra_kwargs = {
            "insurance_company": {
                "help_text": "Name of insurance company (max 100 characters)"
            },
            "policy_number": {
                "help_text": "Insurance policy number (max 50 characters)"
            },
            "insurance_coverage": {"help_text": "Amount covered by insurance"},
            "due_date": {"help_text": "Payment deadline for the bill"},
            "notes": {"help_text": "Additional billing notes and remarks"},
            "terms_and_conditions": {"help_text": "Payment terms and conditions"},
        }

    def validate_appointment_id(self, value: int) -> int:
        """Validate appointment ID exists"""
        if not Appointment.objects.filter(id=value).exists():
            raise serializers.ValidationError("Appointment not found")
        return value

    def validate_insurance_company(self, value: str) -> str:
        """Validate insurance company name"""
        if value and len(value) > 100:
            raise serializers.ValidationError(
                "Insurance company cannot exceed 100 characters"
            )
        return value.strip() if value else value

    def validate_policy_number(self, value: str) -> str:
        """Validate policy number"""
        if value and len(value) > 50:
            raise serializers.ValidationError(
                "Policy number cannot exceed 50 characters"
            )
        return value.strip() if value else value

    def validate_insurance_coverage(self, value: Decimal) -> Decimal:
        """Validate insurance coverage amount"""
        if value and value < 0:
            raise serializers.ValidationError("Insurance coverage cannot be negative")

        if value:
            exponent = value.as_tuple().exponent
            if isinstance(exponent, int) and exponent < -2:
                raise serializers.ValidationError(
                    "Insurance coverage can have maximum 2 decimal places"
                )

        return value or Decimal("0.00")

    def validate_notes(self, value: str) -> str:
        """Validate notes"""
        if value and len(value) > 2000:
            raise serializers.ValidationError("Notes cannot exceed 2000 characters")
        return value.strip() if value else value

    def validate_terms_and_conditions(self, value: str) -> str:
        """Validate terms and conditions"""
        if value and len(value) > 5000:
            raise serializers.ValidationError(
                "Terms and conditions cannot exceed 5000 characters"
            )
        return value.strip() if value else value

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate bill consistency"""
        # Validate that insurance coverage requires insurance company
        if data.get("insurance_coverage", Decimal("0")) > 0:
            if not data.get("insurance_company"):
                raise serializers.ValidationError(
                    {
                        "insurance_company": "Insurance company is required when insurance coverage is provided"
                    }
                )

        return data


class BillUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating bills"""

    class Meta:
        model = Bill
        fields = [
            "insurance_company",
            "policy_number",
            "insurance_coverage",
            "notes",
            "terms_and_conditions",
            "invoice_status",
        ]

    def validate_invoice_status(self, value: str) -> str:
        """Validate invoice status"""
        valid_statuses = [choice[0] for choice in Bill.INVOICE_STATUS_CHOICES]
        if value not in valid_statuses:
            raise serializers.ValidationError(
                f"Invalid invoice status. Must be one of: {', '.join(valid_statuses)}"
            )
        return value

    # Reuse validators from BillCreateSerializer
    validate_insurance_company = BillCreateSerializer.validate_insurance_company
    validate_policy_number = BillCreateSerializer.validate_policy_number
    validate_insurance_coverage = BillCreateSerializer.validate_insurance_coverage
    validate_notes = BillCreateSerializer.validate_notes
    validate_terms_and_conditions = BillCreateSerializer.validate_terms_and_conditions
