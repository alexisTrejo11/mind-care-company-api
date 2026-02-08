from rest_framework import serializers
from decimal import Decimal
from typing import Dict, Any
from apps.billing.models import Bill, BillItem
from apps.appointments.models import Appointment
from apps.users.models import User


class BillItemSerializer(serializers.ModelSerializer):
    """Serializer for bill items"""

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


class BillSerializer(serializers.ModelSerializer):
    """Serializer for reading bill data"""

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


class BillCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating bills"""

    appointment_id = serializers.IntegerField(required=True)

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
