from rest_framework import serializers
from decimal import Decimal
from typing import Dict, Any, List
from apps.billing.models import InsuranceClaim, Bill
from apps.users.models import User


class InsuranceClaimSerializer(serializers.ModelSerializer):
    """Serializer for reading insurance claim data"""

    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)
    bill_number = serializers.CharField(source="bill.bill_number", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    patient_email = serializers.EmailField(source="patient.email", read_only=True)

    class Meta:
        model = InsuranceClaim
        fields = [
            "id",
            "claim_number",
            "bill",
            "bill_number",
            "patient",
            "patient_name",
            "patient_email",
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
            "created_by",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "bill": {"read_only": True},
            "patient": {"read_only": True},
            "created_by": {"read_only": True},
        }


class InsuranceClaimCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating insurance claims"""

    bill_id = serializers.IntegerField(required=True)
    patient_id = serializers.IntegerField(required=True)

    class Meta:
        model = InsuranceClaim
        fields = [
            "bill_id",
            "patient_id",
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
            "date_of_service",
            "notes",
        ]

    def validate_bill_id(self, value: int) -> int:
        """Validate bill ID exists"""
        if not Bill.objects.filter(id=value).exists():
            raise serializers.ValidationError("Bill not found")
        return value

    def validate_patient_id(self, value: int) -> int:
        """Validate patient ID exists"""
        if not User.objects.filter(id=value, user_type="patient").exists():
            raise serializers.ValidationError("Patient not found")
        return value

    def validate_insurance_company(self, value: str) -> str:
        """Validate insurance company name"""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Insurance company is required")
        if len(value) > 100:
            raise serializers.ValidationError(
                "Insurance company cannot exceed 100 characters"
            )
        return value.strip()

    def validate_policy_number(self, value: str) -> str:
        """Validate policy number"""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Policy number is required")
        if len(value) > 50:
            raise serializers.ValidationError(
                "Policy number cannot exceed 50 characters"
            )
        return value.strip()

    def validate_subscriber_name(self, value: str) -> str:
        """Validate subscriber name"""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Subscriber name is required")
        if len(value) > 100:
            raise serializers.ValidationError(
                "Subscriber name cannot exceed 100 characters"
            )
        return value.strip()

    def validate_subscriber_relationship(self, value: str) -> str:
        """Validate subscriber relationship"""
        valid_relationships = ["self", "spouse", "child", "other"]
        if value not in valid_relationships:
            raise serializers.ValidationError(
                f"Invalid relationship. Must be one of: {', '.join(valid_relationships)}"
            )
        return value

    def validate_diagnosis_codes(self, value: List[str]) -> List[str]:
        """Validate diagnosis codes (ICD-10)"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Diagnosis codes must be a list")

        for code in value:
            if not isinstance(code, str) or len(code) > 10:
                raise serializers.ValidationError(
                    f"Invalid diagnosis code format: {code}"
                )

        return value

    def validate_procedure_codes(self, value: List[str]) -> List[str]:
        """Validate procedure codes (CPT/HCPCS)"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Procedure codes must be a list")

        for code in value:
            if not isinstance(code, str) or len(code) > 10:
                raise serializers.ValidationError(
                    f"Invalid procedure code format: {code}"
                )

        return value

    def validate_total_claimed_amount(self, value: Decimal) -> Decimal:
        """Validate claimed amount"""
        if value <= 0:
            raise serializers.ValidationError("Claimed amount must be greater than 0")

        exponent = value.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -2:
            raise serializers.ValidationError(
                "Amount can have maximum 2 decimal places"
            )

        return value

    def validate_insurance_responsibility(self, value: Decimal) -> Decimal:
        """Validate insurance responsibility amount"""
        if value < 0:
            raise serializers.ValidationError(
                "Insurance responsibility cannot be negative"
            )

        exponent = value.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -2:
            raise serializers.ValidationError(
                "Amount can have maximum 2 decimal places"
            )

        return value

    def validate_patient_responsibility(self, value: Decimal) -> Decimal:
        """Validate patient responsibility amount"""
        if value < 0:
            raise serializers.ValidationError(
                "Patient responsibility cannot be negative"
            )

        exponent = value.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -2:
            raise serializers.ValidationError(
                "Amount can have maximum 2 decimal places"
            )

        return value

    def validate_denied_amount(self, value: Decimal) -> Decimal:
        """Validate denied amount"""
        if value < 0:
            raise serializers.ValidationError("Denied amount cannot be negative")

        exponent = value.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -2:
            raise serializers.ValidationError(
                "Amount can have maximum 2 decimal places"
            )

        return value

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate claim consistency"""
        # Validate amount consistency (basic format check, business logic in service)
        total_claimed = data.get("total_claimed_amount", Decimal("0"))
        insurance_resp = data.get("insurance_responsibility", Decimal("0"))
        patient_resp = data.get("patient_responsibility", Decimal("0"))
        denied = data.get("denied_amount", Decimal("0"))

        # Check if amounts add up (basic validation)
        total_calculated = insurance_resp + patient_resp + denied
        if total_claimed > 0 and total_calculated > total_claimed:
            raise serializers.ValidationError(
                {
                    "amounts": "Insurance responsibility + patient responsibility + denied amount cannot exceed total claimed amount"
                }
            )

        return data
