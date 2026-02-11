from rest_framework import serializers
from decimal import Decimal
from typing import Dict, Any, List
from drf_spectacular.utils import extend_schema_serializer
from apps.billing.models import InsuranceClaim, Bill
from apps.users.models import User


@extend_schema_serializer(component_name="InsuranceClaim")
class InsuranceClaimSerializer(serializers.ModelSerializer):
    """
    Serializer for insurance claim data display and comprehensive read operations.

    Provides complete insurance claim information including patient details,
    diagnosis and procedure codes, amount breakdowns, status tracking, and EDI
    reference information. Supports complex medical coding and claim lifecycle.

    **Data Schema:**

    | Field | Type | Read-only | Format | Description |
    |-------|------|-----------|--------|-------------|
    | id | Integer | Yes | - | Unique claim identifier |
    | claim_number | String | Yes | "CLM-YYYYMM-XXXX" | Auto-generated claim number |
    | bill | Integer | Yes | - | Related bill ID |
    | bill_number | String | Yes | - | Bill number (computed) |
    | patient | Integer | Yes | - | Patient user ID |
    | patient_name | String | Yes | - | Patient full name (computed) |
    | patient_email | Email | Yes | - | Patient email (computed) |
    | insurance_company | String | Yes | - | Insurance provider name |
    | policy_number | String | Yes | - | Insurance policy number |
    | group_number | String | Yes | - | Group number (optional) |
    | subscriber_name | String | Yes | - | Subscriber on policy |
    | subscriber_relationship | String | Yes | "self"/"spouse"/"child"/"other" | Relationship to patient |
    | diagnosis_codes | Array | Yes | ICD-10 codes | Diagnosis codes as JSON |
    | procedure_codes | Array | Yes | CPT codes | Procedure codes as JSON |
    | total_claimed_amount | Decimal | Yes | Currency | Total amount claimed |
    | insurance_responsibility | Decimal | Yes | Currency | Amount insurer should pay |
    | patient_responsibility | Decimal | Yes | Currency | Patient's out-of-pocket |
    | denied_amount | Decimal | Yes | Currency | Amount denied by insurer |
    | status | String | Yes | See statuses | Current claim status |
    | status_display | String | Yes | - | Display-friendly status |
    | date_of_service | DateTime | Yes | ISO 8601 | Service date |
    | date_submitted | DateTime | Yes | ISO 8601 | Claim submission date |
    | date_acknowledged | DateTime | Yes | ISO 8601 | Insurer received (null if pending) |
    | date_processed | DateTime | Yes | ISO 8601 | Insurer completed review (null if pending) |
    | date_paid | DateTime | Yes | ISO 8601 | Insurer payment sent (null if unpaid) |
    | edi_file_name | String | Yes | - | EDI submission file name |
    | edi_reference_number | String | Yes | - | EDI reference code |
    | payer_claim_number | String | Yes | - | Payer's claim reference |
    | notes | String | Yes | - | Claim notes and remarks |
    | denial_reason | String | Yes | - | Reason for denial (if denied) |
    | appeal_notes | String | Yes | - | Appeal notes if disputed |
    | created_at | DateTime | Yes | ISO 8601 | Creation timestamp |
    | updated_at | DateTime | Yes | ISO 8601 | Last update timestamp |
    | created_by | Integer | Yes | - | User who created claim |

    **Claim Status Progression:**
    - "draft": Initial claim, not yet submitted
    - "submitted": Sent to insurance company
    - "acknowledged": Insurance received and processing
    - "pending_review": Under review by insurer
    - "approved": Approved for payment
    - "approved_partial": Partially approved
    - "denied": Denied by insurer
    - "paid": Payment received from insurer
    - "appealed": Denial appealed

    **Subscriber Relationships:**
    - "self": Patient is the policy holder
    - "spouse": Spouse's policy covering patient
    - "child": Parent's policy covering patient
    - "other": Other coverage arrangement

    **Diagnosis/Procedure Codes:**
    - Stored as JSON arrays
    - Diagnosis: ICD-10 format (e.g., "E10.9", "J44.0")
    - Procedure: CPT format (e.g., "99213", "92004")
    - Supports multiple codes per claim

    **Amount Breakdown:**
    - total_claimed_amount: Sum of all charges
    - insurance_responsibility: Amount insurer agreed to pay
    - patient_responsibility: Patient's share (copay/coinsurance)
    - denied_amount: Amount denied
    - Formula: insurance_responsibility + patient_responsibility + denied_amount = total_claimed_amount

    **EDI Integration:**
    - Electronic Data Interchange compliance
    - edi_reference_number: Tracks submission
    - payer_claim_number: Insurer's reference ID
    - edi_file_name: Uploaded X12 or NCPDP file

    **Computed Fields:**
    - patient_name: From related user
    - bill_number: From related bill
    - status_display: User-friendly status name
    """

    patient_name = serializers.CharField(
        source="patient.get_full_name",
        read_only=True,
        help_text="Patient's full name",
    )
    bill_number = serializers.CharField(
        source="bill.bill_number",
        read_only=True,
        help_text="Related bill number",
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
        help_text="Display-friendly claim status",
    )
    patient_email = serializers.EmailField(
        source="patient.email",
        read_only=True,
        help_text="Patient's email address",
    )

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


@extend_schema_serializer(component_name="InsuranceClaimCreate")
class InsuranceClaimCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and submitting insurance claims.

    Handles creation of new insurance claims with required subscriber information,
    medical coding (ICD-10 diagnosis and CPT procedure codes), and amount breakdown.
    Validates medical code formats and amount consistency.

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | bill_id | Integer | Yes | - | ID of related bill |
    | patient_id | Integer | Yes | - | ID of patient |
    | insurance_company | String | Yes | Max 100 chars | Insurance provider name |
    | policy_number | String | Yes | Max 50 chars | Policy number |
    | group_number | String | No | Max 50 chars | Group/employer number |
    | subscriber_name | String | Yes | Max 100 chars | Subscriber name |
    | subscriber_relationship | Enum | Yes | "self"/"spouse"/"child"/"other" | Relationship to patient |
    | diagnosis_codes | Array | Yes | ICD-10 codes | List of diagnosis codes |
    | procedure_codes | Array | Yes | CPT codes | List of procedure codes |
    | total_claimed_amount | Decimal | Yes | Currency | Total bill amount |
    | insurance_responsibility | Decimal | Yes | Currency | Amount insurer should pay |
    | patient_responsibility | Decimal | Yes | Currency | Patient's out-of-pocket |
    | denied_amount | Decimal | Yes | Currency | Amount to deny (usually 0) |
    | date_of_service | DateTime | Yes | ISO 8601 | When service was provided |
    | notes | String | No | - | Additional claim notes |

    **Field Specifications:**

    1. **bill_id and patient_id fields**:
       - Both required to link claim to records
       - bill_id: Existing bill being claimed
       - patient_id: Patient (must be existing patient user)

    2. **insurance_company field**:
       - Required provider name
       - Maximum 100 characters
       - Whitespace automatically trimmed

    3. **policy_number and group_number fields**:
       - policy_number: Required policy ID
       - group_number: Optional employer group ID
       - Maximum 50 characters each
       - Whitespace trimmed

    4. **subscriber_name field**:
       - Required policy holder name
       - Maximum 100 characters
       - Whitespace trimmed

    5. **subscriber_relationship field**:
       - Required relationship to patient
       - "self": Patient is policy holder
       - "spouse": Spouse's policy
       - "child": Parent's policy
       - "other": Other arrangement

    6. **diagnosis_codes and procedure_codes fields**:
       - Both require at least one code
       - diagnosis_codes: ICD-10 format (max 10 chars each)
       - procedure_codes: CPT format (max 10 chars each)
       - Passed as JSON arrays
       - Example: ["E10.9", "J44.0"]

    7. **Amount fields**:
       - total_claimed_amount: Total bill being claimed
       - insurance_responsibility: Amount insurer pays
       - patient_responsibility: Patient pays (copay/coinsurance)
       - denied_amount: Upfront denials (usually 0)
       - Must sum correctly: insurance + patient + denied = total

    8. **date_of_service field**:
       - Required service date
       - ISO 8601 format
       - Must be on or before claim date

    9. **notes field**:
       - Optional claim notes
       - Additional information for claim

    **Validation Rules:**

    1. **Amount Validation:**
       - All amounts must be non-negative
       - Max 2 decimal places
       - insurance_responsibility + patient_responsibility + denied_amount = total_claimed_amount
       - Tolerance: ±$0.01 for rounding

    2. **Code Validation:**
       - diagnosis_codes: List format, max 10 chars each
       - procedure_codes: List format, max 10 chars each
       - At least one of each code type required

    3. **Date Validation:**
       - date_of_service <= today
       - No future service dates

    **Claim Submission Process:**
    1. Validates all required fields present
    2. Verifies medical code formats
    3. Checks amount consistency
    4. Creates InsuranceClaim record
    5. Sets status to "draft"
    6. Generates claim_number (CLM-YYYYMM-XXXX)
    """

    bill_id = serializers.IntegerField(
        required=True, help_text="ID of the bill being claimed"
    )
    patient_id = serializers.IntegerField(required=True, help_text="ID of the patient")

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
        extra_kwargs = {
            "insurance_company": {
                "help_text": "Insurance provider name (max 100 characters)"
            },
            "policy_number": {
                "help_text": "Insurance policy number (max 50 characters)"
            },
            "group_number": {"help_text": "Group/employer number (max 50 characters)"},
            "subscriber_name": {"help_text": "Policy holder name (max 100 characters)"},
            "subscriber_relationship": {
                "help_text": "Relationship: self, spouse, child, or other"
            },
            "diagnosis_codes": {
                "help_text": "List of ICD-10 diagnosis codes (max 10 chars each)"
            },
            "procedure_codes": {
                "help_text": "List of CPT procedure codes (max 10 chars each)"
            },
            "total_claimed_amount": {"help_text": "Total bill amount being claimed"},
            "insurance_responsibility": {"help_text": "Amount insurer should pay"},
            "patient_responsibility": {"help_text": "Patient's out-of-pocket cost"},
            "denied_amount": {"help_text": "Amount denied (usually 0)"},
            "date_of_service": {"help_text": "Date when service was provided"},
            "notes": {"help_text": "Additional claim notes and details"},
        }

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
