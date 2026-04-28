import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone

from apps.billing.serializers import (
    InsuranceClaimSerializer,
    InsuranceClaimCreateSerializer,
)
from apps.billing.models import InsuranceClaim, Bill
from apps.appointments.models import Appointment
from apps.users.models import User
from apps.specialists.models import Specialist


class InsuranceClaimSerializerTest(TestCase):
    """Test cases for InsuranceClaimSerializer (read-only)"""

    def setUp(self):
        """Set up test data"""
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            user_type="patient",
            phone="1234567890",
            first_name="John",
            last_name="Doe",
        )

        self.specialist_user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            user_type="specialist",
            phone="0987654321",
        )

        self.specialist = Specialist.objects.create(
            user=self.specialist_user,
            bio="Test specialist",
            consultation_fee=Decimal("100.00"),
            years_experience=5,
        )

        self.appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_date=timezone.now().date() + timedelta(days=1),
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(minutes=30),
            duration_minutes=30,
            appointment_type="online",
            status="completed",
        )

        self.bill = Bill.objects.create(
            appointment=self.appointment,
            patient=self.patient,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("8.50"),
            total_amount=Decimal("108.50"),
            due_date=timezone.now().date() + timedelta(days=14),
            insurance_company="Blue Cross",
            policy_number="BC123456",
            insurance_coverage=Decimal("80.00"),
        )

        self.claim = InsuranceClaim.objects.create(
            bill=self.bill,
            patient=self.patient,
            insurance_company="Blue Cross",
            policy_number="BC123456",
            group_number="GRP123",
            subscriber_name="John Doe",
            subscriber_relationship="self",
            total_claimed_amount=Decimal("108.50"),
            insurance_responsibility=Decimal("86.80"),
            patient_responsibility=Decimal("21.70"),
            status="pending",
            date_of_service=timezone.now().date(),
        )

    def test_serialize_claim_valid(self):
        """Test serializing valid insurance claim"""
        serializer = InsuranceClaimSerializer(self.claim)
        data = serializer.data

        assert data["id"] == self.claim.id
        assert data["claim_number"] == self.claim.claim_number
        assert data["insurance_company"] == "Blue Cross"
        assert data["policy_number"] == "BC123456"
        assert data["patient_name"] == "John Doe"
        assert data["bill_number"] == self.bill.bill_number

    def test_claim_display_fields(self):
        """Test display fields are populated"""
        serializer = InsuranceClaimSerializer(self.claim)
        data = serializer.data

        assert data["status_display"] is not None
        assert data["patient_email"] == self.patient.email

    def test_claim_with_dates(self):
        """Test claim with various date fields"""
        self.claim.date_submitted = timezone.now().date()
        self.claim.date_acknowledged = timezone.now().date() + timedelta(days=1)
        self.claim.date_processed = timezone.now().date() + timedelta(days=7)
        self.claim.date_paid = timezone.now().date() + timedelta(days=10)
        self.claim.save()

        serializer = InsuranceClaimSerializer(self.claim)
        data = serializer.data

        assert data["date_submitted"] is not None
        assert data["date_acknowledged"] is not None
        assert data["date_processed"] is not None
        assert data["date_paid"] is not None

    def test_claim_with_denial_information(self):
        """Test claim with denial details"""
        self.claim.status = "denied"
        self.claim.denied_amount = Decimal("10.00")
        self.claim.denial_reason = "Service not covered"
        self.claim.save()

        serializer = InsuranceClaimSerializer(self.claim)
        data = serializer.data

        assert data["status"] == "denied"
        assert float(data["denied_amount"]) == 10.00
        assert data["denial_reason"] == "Service not covered"

    def test_claim_with_edi_reference(self):
        """Test claim with EDI file information"""
        self.claim.edi_file_name = "claim_batch_20260207.edi"
        self.claim.edi_reference_number = "EDI123456"
        self.claim.payer_claim_number = "PAY123456"
        self.claim.save()

        serializer = InsuranceClaimSerializer(self.claim)
        data = serializer.data

        assert data["edi_file_name"] == "claim_batch_20260207.edi"
        assert data["edi_reference_number"] == "EDI123456"
        assert data["payer_claim_number"] == "PAY123456"


class InsuranceClaimCreateSerializerTest(TestCase):
    """Test cases for InsuranceClaimCreateSerializer"""

    def setUp(self):
        """Set up test data"""
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            user_type="patient",
        )

        self.specialist_user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            user_type="specialist",
            years_experience=5,
        )

        self.specialist = Specialist.objects.create(
            user=self.specialist_user,
            bio="Test specialist",
            consultation_fee=Decimal("100.00"),
            years_experience=5,
        )

        self.appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_date=timezone.now().date() + timedelta(days=1),
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(minutes=30),
            duration_minutes=30,
            appointment_type="online",
            status="completed",
        )

        self.bill = Bill.objects.create(
            appointment=self.appointment,
            patient=self.patient,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("8.50"),
            total_amount=Decimal("108.50"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

    def test_create_claim_valid_minimal(self):
        """Test creating claim with minimal required data"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_claim_valid_full(self):
        """Test creating claim with all fields"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "group_number": "GRP123",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "diagnosis_codes": ["A00.0", "B01.1"],
            "procedure_codes": ["99213", "99214"],
            "total_claimed_amount": Decimal("100.00"),
            "insurance_responsibility": Decimal("80.00"),
            "patient_responsibility": Decimal("20.00"),
            "denied_amount": Decimal("0.00"),
            "date_of_service": timezone.now().date(),
            "notes": "Routine visit",
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_claim_missing_bill_id(self):
        """Test creating claim without bill_id"""
        data = {
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "bill_id" in serializer.errors

    def test_create_claim_invalid_bill_id(self):
        """Test creating claim with non-existent bill"""
        data = {
            "bill_id": 9999,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "bill_id" in serializer.errors

    def test_create_claim_missing_patient_id(self):
        """Test creating claim without patient_id"""
        data = {
            "bill_id": self.bill.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "patient_id" in serializer.errors

    def test_create_claim_invalid_patient_id(self):
        """Test creating claim with non-existent patient"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": 9999,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "patient_id" in serializer.errors

    def test_create_claim_patient_not_patient_type(self):
        """Test creating claim with non-patient user"""
        specialist = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            user_type="specialist",
        )

        data = {
            "bill_id": self.bill.id,
            "patient_id": specialist.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "patient_id" in serializer.errors

    def test_create_claim_missing_insurance_company(self):
        """Test creating claim without insurance company"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            # Missing insurance_company
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "insurance_company" in serializer.errors

    def test_create_claim_empty_insurance_company(self):
        """Test creating claim with empty insurance company"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "   ",  # Only whitespace
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "insurance_company" in serializer.errors

    def test_create_claim_insurance_company_too_long(self):
        """Test insurance company exceeding max length"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "A" * 101,
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "insurance_company" in serializer.errors

    def test_create_claim_missing_policy_number(self):
        """Test creating claim without policy number"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            # Missing policy_number
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "policy_number" in serializer.errors

    def test_create_claim_policy_number_too_long(self):
        """Test policy number exceeding max length"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "A" * 51,
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "policy_number" in serializer.errors

    def test_create_claim_missing_subscriber_name(self):
        """Test creating claim without subscriber name"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            # Missing subscriber_name
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "subscriber_name" in serializer.errors

    def test_create_claim_subscriber_name_too_long(self):
        """Test subscriber name exceeding max length"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "A" * 101,
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "subscriber_name" in serializer.errors

    def test_create_claim_invalid_subscriber_relationship(self):
        """Test claim with invalid subscriber relationship"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "invalid_relationship",
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "subscriber_relationship" in serializer.errors

    def test_create_claim_valid_subscriber_relationships(self):
        """Test all valid subscriber relationships"""
        valid_relationships = ["self", "spouse", "child", "other"]

        for relationship in valid_relationships:
            data = {
                "bill_id": self.bill.id,
                "patient_id": self.patient.id,
                "insurance_company": "Blue Cross",
                "policy_number": "BC123456",
                "subscriber_name": "John Doe",
                "subscriber_relationship": relationship,
                "total_claimed_amount": Decimal("100.00"),
            }

            serializer = InsuranceClaimCreateSerializer(data=data)
            assert (
                serializer.is_valid()
            ), f"Relationship '{relationship}' should be valid"

    def test_create_claim_invalid_diagnosis_codes_not_list(self):
        """Test diagnosis codes that is not a list"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "diagnosis_codes": "A00.0",  # Should be list
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "diagnosis_codes" in serializer.errors

    def test_create_claim_invalid_diagnosis_code_format(self):
        """Test diagnosis code with invalid format"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "diagnosis_codes": ["A" * 11],  # Exceeds 10 chars
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "diagnosis_codes" in serializer.errors

    def test_create_claim_invalid_procedure_codes_not_list(self):
        """Test procedure codes that is not a list"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "procedure_codes": "99213",  # Should be list
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "procedure_codes" in serializer.errors

    def test_create_claim_invalid_procedure_code_format(self):
        """Test procedure code with invalid format"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "procedure_codes": ["A" * 11],  # Exceeds 10 chars
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "procedure_codes" in serializer.errors

    def test_create_claim_zero_claimed_amount(self):
        """Test claim with zero claimed amount"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("0.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "total_claimed_amount" in serializer.errors

    def test_create_claim_negative_claimed_amount(self):
        """Test claim with negative claimed amount"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("-100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "total_claimed_amount" in serializer.errors

    def test_create_claim_claimed_amount_too_many_decimals(self):
        """Test claimed amount with more than 2 decimal places"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.999"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "total_claimed_amount" in serializer.errors

    def test_create_claim_negative_insurance_responsibility(self):
        """Test claim with negative insurance responsibility"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
            "insurance_responsibility": Decimal("-10.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "insurance_responsibility" in serializer.errors

    def test_create_claim_negative_patient_responsibility(self):
        """Test claim with negative patient responsibility"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
            "patient_responsibility": Decimal("-10.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "patient_responsibility" in serializer.errors

    def test_create_claim_negative_denied_amount(self):
        """Test claim with negative denied amount"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
            "denied_amount": Decimal("-10.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "denied_amount" in serializer.errors

    def test_create_claim_amounts_exceed_total(self):
        """Test claim where amounts exceed total claimed"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
            "insurance_responsibility": Decimal("60.00"),
            "patient_responsibility": Decimal("50.00"),
            "denied_amount": Decimal("20.00"),
            # Total: 130.00 > 100.00
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "amounts" in serializer.errors

    def test_create_claim_large_claimed_amount(self):
        """Test claim with large claimed amount"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("99999.99"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_claim_small_claimed_amount(self):
        """Test claim with small claimed amount"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "subscriber_name": "John Doe",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("0.01"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_claim_whitespace_trimmed(self):
        """Test whitespace trimming on string fields"""
        data = {
            "bill_id": self.bill.id,
            "patient_id": self.patient.id,
            "insurance_company": "  Blue Cross  ",
            "policy_number": "  BC123456  ",
            "subscriber_name": "  John Doe  ",
            "subscriber_relationship": "self",
            "total_claimed_amount": Decimal("100.00"),
        }

        serializer = InsuranceClaimCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        assert serializer.validated_data["insurance_company"] == "Blue Cross"
        assert serializer.validated_data["policy_number"] == "BC123456"
        assert serializer.validated_data["subscriber_name"] == "John Doe"
