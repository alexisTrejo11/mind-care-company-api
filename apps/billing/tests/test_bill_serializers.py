import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.billing.serializers import (
    BillItemSerializer,
    BillSerializer,
    BillCreateSerializer,
    BillUpdateSerializer,
)
from apps.billing.models import Bill, BillItem
from apps.appointments.models import Appointment
from apps.users.models import User
from apps.specialists.models import Specialist


class BillItemSerializerTest(TestCase):
    """Test cases for BillItemSerializer"""

    def setUp(self):
        """Set up test data"""
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            user_type="patient",
            phone="1234567890",
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
            rating=4.5,
            years_experience=10,
        )

        self.appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_date=timezone.now().date() + timedelta(days=1),
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(minutes=60),
            duration_minutes=60,
            appointment_type="online",
            status="completed",
        )

        self.bill = Bill.objects.create(
            appointment=self.appointment,
            patient=self.patient,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("8.50"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("108.50"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

        self.bill_item = BillItem.objects.create(
            bill=self.bill,
            description="Consultation Service",
            quantity=1,
            unit_price=Decimal("100.00"),
            tax_rate=Decimal("8.5"),
            discount_rate=Decimal("0.0"),
        )

    def test_serialize_bill_item_valid(self):
        """Test serializing valid bill item"""
        serializer = BillItemSerializer(self.bill_item)
        data = serializer.data

        assert data["id"] == self.bill_item.id
        assert data["description"] == "Consultation Service"
        assert float(data["quantity"]) == 1.0
        assert float(data["unit_price"]) == 100.0
        assert float(data["tax_rate"]) == 8.5
        assert float(data["discount_rate"]) == 0.0

    def test_bill_item_all_fields_read_only(self):
        """Test that all BillItem fields are read-only"""
        serializer = BillItemSerializer(self.bill_item)

        # All fields should be in read_only_fields
        expected_read_only = [
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

        assert serializer.Meta.read_only_fields == expected_read_only

    def test_bill_item_with_service_relationship(self):
        """Test bill item with service relationship"""
        # BillItem can have optional service
        serializer = BillItemSerializer(self.bill_item)
        data = serializer.data

        assert "service" in data
        assert data["service"] is None  # No service linked


class BillSerializerTest(TestCase):
    """Test cases for BillSerializer (read-only)"""

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
            first_name="Dr.",
            last_name="Smith",
        )

        self.specialist = Specialist.objects.create(
            user=self.specialist_user,
            bio="Test specialist",
            consultation_fee=Decimal("150.00"),
            rating=4.8,
            years_experience=15,
        )

        self.appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_date=timezone.now().date() + timedelta(days=1),
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(minutes=60),
            duration_minutes=60,
            appointment_type="in_person",
            status="completed",
        )

        self.bill = Bill.objects.create(
            appointment=self.appointment,
            patient=self.patient,
            subtotal=Decimal("150.00"),
            tax_amount=Decimal("12.75"),
            discount_amount=Decimal("10.00"),
            total_amount=Decimal("152.75"),
            due_date=timezone.now().date() + timedelta(days=14),
            insurance_company="Blue Cross",
            policy_number="BC123456",
            insurance_coverage=Decimal("100.00"),
        )

        BillItem.objects.create(
            bill=self.bill,
            description="Consultation - In Person",
            quantity=1,
            unit_price=Decimal("150.00"),
            tax_rate=Decimal("8.5"),
            discount_rate=Decimal("0.0"),
        )

    def test_serialize_bill_valid(self):
        """Test serializing valid bill"""
        serializer = BillSerializer(self.bill)
        data = serializer.data

        assert data["bill_number"] == self.bill.bill_number
        assert data["patient"] == self.patient.id
        assert data["patient_name"] == "John Doe"
        assert data["patient_email"] == "patient@test.com"
        assert data["specialist_name"] == "Dr. Smith"
        assert float(data["subtotal"]) == 150.0
        assert float(data["total_amount"]) == 152.75

    def test_bill_computed_fields(self):
        """Test computed fields in serializer"""
        serializer = BillSerializer(self.bill)
        data = serializer.data

        assert data["invoice_status_display"] == "Draft"
        assert float(data["amount_paid"]) == 0.0
        assert float(data["balance_due"]) == 152.75
        assert data["payment_count"] == 0

    def test_bill_insurance_information(self):
        """Test insurance information in serializer"""
        serializer = BillSerializer(self.bill)
        data = serializer.data

        assert data["insurance_company"] == "Blue Cross"
        assert data["policy_number"] == "BC123456"
        assert float(data["insurance_coverage"]) == 100.0

    def test_bill_with_multiple_items(self):
        """Test bill serialization with multiple items"""
        BillItem.objects.create(
            bill=self.bill,
            description="Lab Test",
            quantity=1,
            unit_price=Decimal("50.00"),
            tax_rate=Decimal("8.5"),
        )

        serializer = BillSerializer(self.bill)
        data = serializer.data

        assert len(data["items"]) == 2
        assert data["payment_count"] == 0

    def test_bill_with_zero_balance(self):
        """Test bill with zero balance due"""
        from apps.billing.models import Payment

        Payment.objects.create(
            bill=self.bill,
            patient=self.patient,
            amount=self.bill.total_amount,
            payment_method="cash",
            status="completed",
        )

        self.bill.refresh_from_db()
        serializer = BillSerializer(self.bill)
        data = serializer.data

        assert float(data["balance_due"]) == 0.0


class BillCreateSerializerTest(TestCase):
    """Test cases for BillCreateSerializer"""

    def setUp(self):
        """Set up test data"""
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            user_type="patient",
            phone="1234567890",
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
            years_experience=10,
        )

        self.appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_date=timezone.now().date() + timedelta(days=1),
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(minutes=60),
            duration_minutes=60,
            appointment_type="online",
            status="completed",
        )

    def test_create_bill_valid_minimal_data(self):
        """Test creating bill with minimal valid data"""
        data = {
            "appointment_id": self.appointment.id,
            "due_date": timezone.now().date() + timedelta(days=14),
        }

        serializer = BillCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_bill_valid_with_insurance(self):
        """Test creating bill with insurance information"""
        data = {
            "appointment_id": self.appointment.id,
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "insurance_coverage": Decimal("100.00"),
            "due_date": timezone.now().date() + timedelta(days=30),
        }

        serializer = BillCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_bill_valid_with_due_date(self):
        """Test creating bill with custom due date"""
        due_date = (timezone.now() + timedelta(days=30)).date()
        data = {
            "appointment_id": self.appointment.id,
            "due_date": due_date,
        }

        serializer = BillCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["due_date"] == due_date

    def test_create_bill_missing_appointment_id(self):
        """Test creating bill without appointment_id fails"""
        data = {
            "insurance_company": "Blue Cross",
        }

        serializer = BillCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "appointment_id" in serializer.errors

    def test_create_bill_invalid_appointment_id(self):
        """Test creating bill with non-existent appointment fails"""
        data = {
            "appointment_id": 9999,
        }

        serializer = BillCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "appointment_id" in serializer.errors

    def test_create_bill_invalid_appointment_id_type(self):
        """Test creating bill with invalid appointment_id type"""
        data = {
            "appointment_id": "invalid",
        }

        serializer = BillCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "appointment_id" in serializer.errors

    def test_create_bill_insurance_company_too_long(self):
        """Test validation of insurance company name length"""
        data = {
            "appointment_id": self.appointment.id,
            "insurance_company": "A" * 101,  # Exceeds 100 character limit
        }

        serializer = BillCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "insurance_company" in serializer.errors

    def test_create_bill_policy_number_too_long(self):
        """Test validation of policy number length"""
        data = {
            "appointment_id": self.appointment.id,
            "policy_number": "P" * 51,  # Exceeds 50 character limit
        }

        serializer = BillCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "policy_number" in serializer.errors

    def test_create_bill_negative_insurance_coverage(self):
        """Test that negative insurance coverage is rejected"""
        data = {
            "appointment_id": self.appointment.id,
            "insurance_coverage": Decimal("-100.00"),
        }

        serializer = BillCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "insurance_coverage" in serializer.errors

    def test_create_bill_insurance_coverage_validation_decimal_precision(self):
        """Test insurance coverage decimal precision validation"""
        data = {
            "appointment_id": self.appointment.id,
            "insurance_coverage": Decimal("100.999"),  # More than 2 decimals
        }

        serializer = BillCreateSerializer(data=data)
        # This should be rejected due to precision validation
        assert (
            not serializer.is_valid()
            or float(serializer.validated_data.get("insurance_coverage", 0)) <= 100.99
        )

    def test_create_bill_insurance_coverage_requires_company(self):
        """Test that insurance coverage requires insurance company"""
        data = {
            "appointment_id": self.appointment.id,
            "insurance_coverage": Decimal("100.00"),
            "due_date": timezone.now().date() + timedelta(days=14),
            # Missing insurance_company
        }

        serializer = BillCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "insurance_company" in serializer.errors

    def test_create_bill_insurance_company_without_coverage(self):
        """Test insurance company without coverage is valid"""
        data = {
            "appointment_id": self.appointment.id,
            "insurance_company": "Blue Cross",
            "due_date": timezone.now().date() + timedelta(days=14),
            # No insurance_coverage
        }

        serializer = BillCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_bill_notes_too_long(self):
        """Test validation of notes length"""
        data = {
            "appointment_id": self.appointment.id,
            "notes": "A" * 2001,  # Exceeds 2000 character limit
        }

        serializer = BillCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "notes" in serializer.errors

    def test_create_bill_terms_and_conditions_too_long(self):
        """Test validation of terms and conditions length"""
        data = {
            "appointment_id": self.appointment.id,
            "terms_and_conditions": "T" * 5001,  # Exceeds 5000 character limit
        }

        serializer = BillCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "terms_and_conditions" in serializer.errors

    def test_create_bill_whitespace_trimming(self):
        """Test that whitespace is trimmed from string fields"""
        data = {
            "appointment_id": self.appointment.id,
            "insurance_company": "  Blue Cross  ",
            "policy_number": "  BC123456  ",
            "notes": "  Some notes  ",
            "due_date": timezone.now().date() + timedelta(days=14),
        }

        serializer = BillCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        assert serializer.validated_data["insurance_company"] == "Blue Cross"
        assert serializer.validated_data["policy_number"] == "BC123456"
        assert serializer.validated_data["notes"] == "Some notes"

    def test_create_bill_empty_optional_fields(self):
        """Test that optional fields can be empty"""
        data = {
            "appointment_id": self.appointment.id,
            "insurance_company": "",
            "policy_number": "",
            "notes": "",
            "terms_and_conditions": "",
            "due_date": timezone.now().date() + timedelta(days=14),
        }

        serializer = BillCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_bill_zero_insurance_coverage(self):
        """Test that zero insurance coverage is valid"""
        data = {
            "appointment_id": self.appointment.id,
            "insurance_coverage": Decimal("0.00"),
            "due_date": timezone.now().date() + timedelta(days=30),
        }

        serializer = BillCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_bill_large_insurance_coverage(self):
        """Test bill with large insurance coverage amount"""
        data = {
            "appointment_id": self.appointment.id,
            "insurance_company": "Premium Insurance",
            "insurance_coverage": Decimal("999999.99"),
            "due_date": timezone.now().date() + timedelta(days=30),
        }

        serializer = BillCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors


class BillUpdateSerializerTest(TestCase):
    """Test cases for BillUpdateSerializer"""

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
        )

        self.specialist = Specialist.objects.create(
            user=self.specialist_user,
            bio="Test specialist",
            consultation_fee=Decimal("100.00"),
            years_experience=10,
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

    def test_update_bill_insurance_information(self):
        """Test updating bill insurance information"""
        data = {
            "insurance_company": "Blue Cross",
            "policy_number": "BC123456",
            "insurance_coverage": Decimal("50.00"),
        }

        serializer = BillUpdateSerializer(self.bill, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors

    def test_update_bill_notes(self):
        """Test updating bill notes"""
        data = {
            "notes": "Updated notes for this bill",
        }

        serializer = BillUpdateSerializer(self.bill, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors

    def test_update_bill_status_valid(self):
        """Test updating bill status to valid value"""
        data = {
            "invoice_status": "sent",
        }

        serializer = BillUpdateSerializer(self.bill, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors

    def test_update_bill_status_invalid(self):
        """Test updating bill status to invalid value"""
        data = {
            "invoice_status": "invalid_status",
        }

        serializer = BillUpdateSerializer(self.bill, data=data, partial=True)
        assert not serializer.is_valid()
        assert "invoice_status" in serializer.errors

    def test_update_bill_status_all_valid_values(self):
        """Test all valid bill statuses"""
        valid_statuses = ["draft", "sent", "viewed", "paid", "overdue", "cancelled"]

        for status in valid_statuses:
            data = {"invoice_status": status}
            serializer = BillUpdateSerializer(self.bill, data=data, partial=True)
            assert serializer.is_valid(), f"Status '{status}' should be valid"

    def test_update_bill_negative_insurance_coverage_fails(self):
        """Test that negative insurance coverage is rejected on update"""
        data = {
            "insurance_coverage": Decimal("-100.00"),
        }

        serializer = BillUpdateSerializer(self.bill, data=data, partial=True)
        assert not serializer.is_valid()
        assert "insurance_coverage" in serializer.errors

    def test_update_bill_insurance_company_too_long_fails(self):
        """Test that oversized insurance company is rejected on update"""
        data = {
            "insurance_company": "A" * 101,
        }

        serializer = BillUpdateSerializer(self.bill, data=data, partial=True)
        assert not serializer.is_valid()
        assert "insurance_company" in serializer.errors

    def test_update_bill_multiple_fields(self):
        """Test updating multiple fields at once"""
        data = {
            "insurance_company": "Aetna",
            "policy_number": "AE789012",
            "insurance_coverage": Decimal("75.00"),
            "notes": "Updated with new insurance info",
            "invoice_status": "sent",
        }

        serializer = BillUpdateSerializer(self.bill, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors

    def test_update_bill_partial_update(self):
        """Test partial update (not all fields required)"""
        data = {
            "notes": "Just updating notes",
        }

        serializer = BillUpdateSerializer(self.bill, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors

    def test_update_bill_empty_data(self):
        """Test update with empty data on partial update"""
        data = {}

        serializer = BillUpdateSerializer(self.bill, data=data, partial=True)
        assert serializer.is_valid()

    def test_update_bill_whitespace_trimmed(self):
        """Test that whitespace is trimmed on update"""
        data = {
            "insurance_company": "  New Company  ",
            "notes": "  Updated notes  ",
        }

        serializer = BillUpdateSerializer(self.bill, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors

        assert serializer.validated_data["insurance_company"] == "New Company"
        assert serializer.validated_data["notes"] == "Updated notes"

    def test_update_bill_terms_and_conditions(self):
        """Test updating terms and conditions"""
        terms = "These are the terms and conditions for this invoice."
        data = {
            "terms_and_conditions": terms,
        }

        serializer = BillUpdateSerializer(self.bill, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["terms_and_conditions"] == terms

    def test_update_bill_clear_insurance_info(self):
        """Test clearing insurance information"""
        # First set insurance info
        self.bill.insurance_company = "Blue Cross"
        self.bill.policy_number = "BC123456"
        self.bill.save()

        # Now clear it
        data = {
            "insurance_company": "",
            "policy_number": "",
        }

        serializer = BillUpdateSerializer(self.bill, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors

    def test_update_bill_cannot_update_readonly_fields(self):
        """Test that readonly fields cannot be updated"""
        # These fields should be readonly but let's test passing them
        data = {
            "subtotal": Decimal("200.00"),
            "total_amount": Decimal("250.00"),
            "amount_paid": Decimal("100.00"),
        }

        serializer = BillUpdateSerializer(self.bill, data=data, partial=True)
        # Fields not in the serializer's fields list should be ignored
        assert serializer.is_valid()
        # The values in serializer.validated_data should not include readonly fields
        for field in ["subtotal", "total_amount", "amount_paid"]:
            assert field not in serializer.validated_data


class BillSerializerIntegrationTest(TestCase):
    """Integration tests for bill serializers"""

    def setUp(self):
        """Set up test data"""
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            user_type="patient",
            first_name="Jane",
            last_name="Smith",
        )

        self.specialist_user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            user_type="specialist",
            first_name="Dr.",
            last_name="Johnson",
        )

        self.specialist = Specialist.objects.create(
            user=self.specialist_user,
            bio="Expert specialist",
            consultation_fee=Decimal("200.00"),
            years_experience=20,
        )

    def test_create_and_read_bill_flow(self):
        """Test creating a bill and then reading it"""
        # Create appointment first
        appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_date=timezone.now().date() + timedelta(days=1),
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(minutes=60),
            duration_minutes=60,
            appointment_type="in_person",
            status="completed",
        )

        # Create bill using serializer
        create_data = {
            "appointment_id": appointment.id,
            "insurance_company": "United Healthcare",
            "policy_number": "UH456789",
            "insurance_coverage": Decimal("150.00"),
            "notes": "Insurance coverage includes specialist consultation",
            "due_date": timezone.now().date() + timedelta(days=14),
        }

        create_serializer = BillCreateSerializer(data=create_data)
        assert create_serializer.is_valid(), create_serializer.errors

        # Get the bill (would be created by service layer)
        bill = Bill.objects.create(
            appointment=appointment,
            patient=self.patient,
            subtotal=Decimal("200.00"),
            tax_amount=Decimal("17.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("217.00"),
            insurance_company="United Healthcare",
            policy_number="UH456789",
            insurance_coverage=Decimal("150.00"),
            notes="Insurance coverage includes specialist consultation",
            due_date=timezone.now().date() + timedelta(days=14),
        )

        # Read bill using serializer
        read_serializer = BillSerializer(bill)
        data = read_serializer.data

        assert data["insurance_company"] == "United Healthcare"
        assert data["policy_number"] == "UH456789"
        assert float(data["insurance_coverage"]) == 150.0

    def test_update_bill_status_workflow(self):
        """Test updating bill statuses through workflow"""
        appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_date=timezone.now().date() + timedelta(days=1),
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(minutes=45),
            duration_minutes=45,
            appointment_type="online",
            status="completed",
        )

        bill = Bill.objects.create(
            appointment=appointment,
            patient=self.patient,
            subtotal=Decimal("200.00"),
            tax_amount=Decimal("17.00"),
            total_amount=Decimal("217.00"),
            invoice_status="draft",
            due_date=timezone.now().date() + timedelta(days=14),
        )

        # Workflow: draft -> sent -> viewed -> paid
        statuses_to_test = ["draft", "sent", "viewed", "paid"]

        for status in statuses_to_test:
            data = {"invoice_status": status}
            serializer = BillUpdateSerializer(bill, data=data, partial=True)
            assert serializer.is_valid(), f"Failed to validate status: {status}"

    def test_edge_case_very_large_amounts(self):
        """Test handling of very large amounts"""
        appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_date=timezone.now().date() + timedelta(days=1),
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(minutes=30),
            duration_minutes=30,
            appointment_type="online",
            status="completed",
        )

        bill = Bill.objects.create(
            appointment=appointment,
            patient=self.patient,
            subtotal=Decimal("999999.99"),
            tax_amount=Decimal("84999.99"),
            total_amount=Decimal("1084999.98"),
            due_date=timezone.now().date() + timedelta(days=14),
        )
        serializer = BillSerializer(bill)
        data = serializer.data

        assert float(data["subtotal"]) == 999999.99
        assert float(data["total_amount"]) == 1084999.98

    def test_edge_case_very_small_amounts(self):
        """Test handling of very small amounts"""
        appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_date=timezone.now().date() + timedelta(days=1),
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(minutes=15),
            duration_minutes=15,
            appointment_type="online",
            status="completed",
        )

        bill = Bill.objects.create(
            appointment=appointment,
            patient=self.patient,
            subtotal=Decimal("0.50"),
            tax_amount=Decimal("0.04"),
            total_amount=Decimal("0.54"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

        serializer = BillSerializer(bill)
        data = serializer.data

        assert float(data["subtotal"]) == 0.50
        assert float(data["total_amount"]) == 0.54
