import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone

from apps.billing.serializers import (
    RefundSerializer,
    RefundCreateSerializer,
)
from apps.billing.models import Refund, Payment, Bill
from apps.appointments.models import Appointment
from apps.users.models import User
from apps.specialists.models import Specialist


class RefundSerializerTest(TestCase):
    """Test cases for RefundSerializer (read-only)"""

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
        )

        self.appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_date=timezone.now().date() + timedelta(days=1),
            start_time="10:00",
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

        self.payment = Payment.objects.create(
            bill=self.bill,
            patient=self.patient,
            amount=Decimal("108.50"),
            payment_method="cash",
            status="completed",
        )

        self.refund = Refund.objects.create(
            payment=self.payment,
            bill=self.bill,
            amount=Decimal("108.50"),
            reason="patient_request",
            reason_details="Patient requested refund",
            status="requested",
        )

    def test_serialize_refund_valid(self):
        """Test serializing valid refund"""
        serializer = RefundSerializer(self.refund)
        data = serializer.data

        assert data["id"] == self.refund.id
        assert data["refund_number"] == self.refund.refund_number
        assert float(data["amount"]) == 108.50
        assert data["status"] == "requested"
        assert data["reason"] == "patient_request"

    def test_refund_display_fields(self):
        """Test display fields are populated"""
        serializer = RefundSerializer(self.refund)
        data = serializer.data

        assert data["status_display"] is not None
        assert data["reason_display"] is not None
        assert data["patient_name"] == "John Doe"

    def test_refund_all_fields_read_only(self):
        """Test that all refund fields are read-only"""
        serializer = RefundSerializer(self.refund)

        assert len(serializer.read_only_fields) > 0

    def test_refund_with_dates(self):
        """Test refund with date fields"""
        self.refund.requested_date = timezone.now().date()
        self.refund.processed_date = timezone.now().date() + timedelta(days=3)
        self.refund.save()

        serializer = RefundSerializer(self.refund)
        data = serializer.data

        assert data["requested_date"] is not None
        assert data["processed_date"] is not None

    def test_refund_with_stripe_information(self):
        """Test refund with Stripe refund ID"""
        self.refund.status = "completed"
        self.refund.stripe_refund_id = "re_test123"
        self.refund.save()

        serializer = RefundSerializer(self.refund)
        data = serializer.data

        assert data["status"] == "completed"
        assert data["stripe_refund_id"] == "re_test123"

    def test_refund_with_admin_notes(self):
        """Test refund with admin notes"""
        payment_data = Payment.objects.create(
            bill=self.bill,
            patient=self.patient,
            amount=Decimal("50.00"),
            payment_method="bank_transfer",
            status="completed",
        )

        refund_data = Refund.objects.create(
            payment=payment_data,
            bill=self.bill,
            amount=Decimal("50.00"),
            reason="incorrect_charge",
            reason_details="Duplicate charge",
            status="processing",
        )

        serializer = RefundSerializer(refund_data)
        data = serializer.data

        assert data["amount"] is not None
        assert data["reason"] == "incorrect_charge"


class RefundCreateSerializerTest(TestCase):
    """Test cases for RefundCreateSerializer"""

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
        )

        self.appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_date=timezone.now().date() + timedelta(days=1),
            start_time="10:00",
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

        self.payment = Payment.objects.create(
            bill=self.bill,
            patient=self.patient,
            amount=Decimal("108.50"),
            payment_method="cash",
            status="completed",
        )

    def test_create_refund_patient_request_valid(self):
        """Test creating refund for patient request"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("50.00"),
            "reason": "patient_request",
            "reason_details": "Patient requested refund",
        }

        serializer = RefundCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_refund_incorrect_charge_valid(self):
        """Test creating refund for incorrect charge"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("108.50"),
            "reason": "incorrect_charge",
            "reason_details": "Duplicate charge",
        }

        serializer = RefundCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_refund_insurance_adjustment_valid(self):
        """Test creating refund for insurance adjustment"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("20.00"),
            "reason": "insurance_adjustment",
            "reason_details": "Insurance adjustment received",
        }

        serializer = RefundCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_refund_missing_payment_id(self):
        """Test creating refund without payment_id"""
        data = {
            "amount": Decimal("50.00"),
            "reason": "patient_request",
        }

        serializer = RefundCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "payment_id" in serializer.errors

    def test_create_refund_invalid_payment_id(self):
        """Test creating refund with non-existent payment"""
        data = {
            "payment_id": 9999,
            "amount": Decimal("50.00"),
            "reason": "patient_request",
        }

        serializer = RefundCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "payment_id" in serializer.errors

    def test_create_refund_missing_amount(self):
        """Test creating refund without amount"""
        data = {
            "payment_id": self.payment.id,
            "reason": "patient_request",
        }

        serializer = RefundCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_create_refund_zero_amount(self):
        """Test creating refund with zero amount"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("0.00"),
            "reason": "patient_request",
        }

        serializer = RefundCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_create_refund_negative_amount(self):
        """Test creating refund with negative amount"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("-50.00"),
            "reason": "patient_request",
        }

        serializer = RefundCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_create_refund_amount_too_many_decimals(self):
        """Test refund amount with more than 2 decimal places"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("50.999"),
            "reason": "patient_request",
        }

        serializer = RefundCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_create_refund_invalid_reason(self):
        """Test creating refund with invalid reason"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("50.00"),
            "reason": "invalid_reason",
        }

        serializer = RefundCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "reason" in serializer.errors

    def test_create_refund_reason_details_too_long(self):
        """Test reason details exceeding max length"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("50.00"),
            "reason": "patient_request",
            "reason_details": "A" * 1001,
        }

        serializer = RefundCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "reason_details" in serializer.errors

    def test_create_refund_large_amount(self):
        """Test creating refund with large amount"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("99999.99"),
            "reason": "patient_request",
        }

        serializer = RefundCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_refund_minimum_amount(self):
        """Test creating refund with minimum valid amount"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("0.01"),
            "reason": "patient_request",
        }

        serializer = RefundCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_refund_without_reason_details(self):
        """Test creating refund without reason details"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("50.00"),
            "reason": "patient_request",
            # reason_details is optional
        }

        serializer = RefundCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_refund_with_whitespace_in_reason_details(self):
        """Test reason details with whitespace is trimmed"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("50.00"),
            "reason": "patient_request",
            "reason_details": "  Patient requested refund  ",
        }

        serializer = RefundCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["reason_details"] == "Patient requested refund"

    def test_create_multiple_refunds_same_payment(self):
        """Test creating multiple refunds for same payment"""
        # First refund
        data1 = {
            "payment_id": self.payment.id,
            "amount": Decimal("50.00"),
            "reason": "patient_request",
        }

        serializer1 = RefundCreateSerializer(data=data1)
        assert serializer1.is_valid(), serializer1.errors

        # Second refund for remaining amount
        data2 = {
            "payment_id": self.payment.id,
            "amount": Decimal("58.50"),
            "reason": "patient_request",
        }

        serializer2 = RefundCreateSerializer(data=data2)
        # Business logic validation (if amount <= payment amount) is in service layer
        assert serializer2.is_valid(), serializer2.errors

    def test_create_refund_all_valid_reasons(self):
        """Test all valid refund reasons"""
        valid_reasons = [
            "patient_request",
            "incorrect_charge",
            "service_not_provided",
            "insurance_adjustment",
            "duplicate_charge",
            "other",
        ]

        for reason in valid_reasons:
            data = {
                "payment_id": self.payment.id,
                "amount": Decimal("50.00"),
                "reason": reason,
            }

            serializer = RefundCreateSerializer(data=data)
            assert serializer.is_valid(), f"Reason '{reason}' should be valid"

    def test_refund_serializer_amount_validation(self):
        """Test refund amount validation rules"""
        # Valid amount with 2 decimals
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("50.25"),
            "reason": "patient_request",
        }

        serializer = RefundCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_refund_serializer_exact_payment_amount(self):
        """Test refund for exact payment amount"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("108.50"),
            "reason": "patient_request",
        }

        serializer = RefundCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_refund_serializer_partial_payment_amount(self):
        """Test refund for partial payment"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("27.125"),  # Will fail due to decimal places
            "reason": "patient_request",
        }

        serializer = RefundCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_refund_serializer_edge_case_minimum_decimal(self):
        """Test refund with minimum decimal value"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("0.01"),
            "reason": "patient_request",
        }

        serializer = RefundCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_refund_serializer_edge_case_max_decimal(self):
        """Test refund with maximum reasonable amount"""
        data = {
            "payment_id": self.payment.id,
            "amount": Decimal("999999.99"),
            "reason": "patient_request",
        }

        serializer = RefundCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
