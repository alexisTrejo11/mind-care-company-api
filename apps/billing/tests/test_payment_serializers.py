import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone

from apps.billing.serializers import (
    PaymentSerializer,
    PaymentCreateSerializer,
    OnlinePaymentIntentSerializer,
    PaymentMethodSerializer,
    PaymentMethodCreateSerializer,
)
from apps.billing.models import Payment, PaymentMethod, Bill
from apps.appointments.models import Appointment
from apps.users.models import User
from apps.specialists.models import Specialist


class PaymentSerializerTest(TestCase):
    """Test cases for PaymentSerializer (read-only)"""

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
        )

        self.payment = Payment.objects.create(
            bill=self.bill,
            patient=self.patient,
            amount=Decimal("108.50"),
            payment_method="cash",
            status="completed",
        )

    def test_serialize_payment_valid(self):
        """Test serializing valid payment"""
        serializer = PaymentSerializer(self.payment)
        data = serializer.data

        assert data["id"] == self.payment.id
        assert data["payment_number"] == self.payment.payment_number
        assert float(data["amount"]) == 108.50
        assert data["status"] == "completed"
        assert data["patient_name"] == "John Doe"
        assert data["bill_number"] == self.bill.bill_number

    def test_payment_display_fields(self):
        """Test display fields are populated"""
        serializer = PaymentSerializer(self.payment)
        data = serializer.data

        assert data["status_display"] is not None
        assert data["payment_method_display"] is not None

    def test_payment_with_stripe_details(self):
        """Test payment with Stripe details"""
        self.payment.stripe_payment_intent_id = "pi_test123"
        self.payment.stripe_charge_id = "ch_test123"
        self.payment.card_last4 = "4242"
        self.payment.card_brand = "visa"
        self.payment.save()

        serializer = PaymentSerializer(self.payment)
        data = serializer.data

        assert data["stripe_payment_intent_id"] == "pi_test123"
        assert data["stripe_charge_id"] == "ch_test123"
        assert data["card_last4"] == "4242"
        assert data["card_brand"] == "visa"

    def test_payment_with_bank_details(self):
        """Test payment with bank transfer details"""
        self.payment.payment_method = "bank_transfer"
        self.payment.bank_reference = "TRANS123456"
        self.payment.bank_name = "Test Bank"
        self.payment.save()

        serializer = PaymentSerializer(self.payment)
        data = serializer.data

        assert data["bank_reference"] == "TRANS123456"
        assert data["bank_name"] == "Test Bank"


class PaymentCreateSerializerTest(TestCase):
    """Test cases for PaymentCreateSerializer"""

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

    def test_create_cash_payment_valid(self):
        """Test creating valid cash payment"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("50.00"),
            "payment_method": "cash",
        }

        serializer = PaymentCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_bank_transfer_payment_valid(self):
        """Test creating valid bank transfer payment"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("100.00"),
            "payment_method": "bank_transfer",
            "bank_reference": "TRANSFER123",
            "bank_name": "Test Bank",
        }

        serializer = PaymentCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_online_payment_valid(self):
        """Test creating valid online payment"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("108.50"),
            "payment_method": "online",
        }

        serializer = PaymentCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_payment_missing_bill_id(self):
        """Test creating payment without bill_id"""
        data = {
            "amount": Decimal("50.00"),
            "payment_method": "cash",
        }

        serializer = PaymentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "bill_id" in serializer.errors

    def test_create_payment_invalid_bill_id(self):
        """Test creating payment with non-existent bill"""
        data = {
            "bill_id": 9999,
            "amount": Decimal("50.00"),
            "payment_method": "cash",
        }

        serializer = PaymentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "bill_id" in serializer.errors

    def test_create_payment_missing_amount(self):
        """Test creating payment without amount"""
        data = {
            "bill_id": self.bill.id,
            "payment_method": "cash",
        }

        serializer = PaymentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_create_payment_zero_amount(self):
        """Test creating payment with zero amount"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("0.00"),
            "payment_method": "cash",
        }

        serializer = PaymentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_create_payment_negative_amount(self):
        """Test creating payment with negative amount"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("-50.00"),
            "payment_method": "cash",
        }

        serializer = PaymentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_create_payment_amount_decimal_precision(self):
        """Test payment amount with more than 2 decimal places"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("50.999"),
            "payment_method": "cash",
        }

        serializer = PaymentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_create_payment_invalid_payment_method(self):
        """Test creating payment with invalid payment method"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("50.00"),
            "payment_method": "invalid_method",
        }

        serializer = PaymentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "payment_method" in serializer.errors

    def test_create_bank_transfer_missing_reference(self):
        """Test bank transfer without reference fails"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("100.00"),
            "payment_method": "bank_transfer",
            "bank_name": "Test Bank",
            # Missing bank_reference
        }

        serializer = PaymentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "bank_reference" in serializer.errors

    def test_create_bank_transfer_missing_bank_name(self):
        """Test bank transfer without bank name fails"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("100.00"),
            "payment_method": "bank_transfer",
            "bank_reference": "TRANS123",
            # Missing bank_name
        }

        serializer = PaymentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "bank_name" in serializer.errors

    def test_create_online_payment_with_bank_details_fails(self):
        """Test online payment with bank details fails"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("100.00"),
            "payment_method": "online",
            "bank_reference": "TRANS123",  # Should not be provided
        }

        serializer = PaymentCreateSerializer(data=data)
        assert not serializer.is_valid()

    def test_create_payment_bank_reference_too_long(self):
        """Test bank reference exceeding max length"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("100.00"),
            "payment_method": "bank_transfer",
            "bank_reference": "A" * 101,
            "bank_name": "Test Bank",
        }

        serializer = PaymentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "bank_reference" in serializer.errors

    def test_create_payment_bank_name_too_long(self):
        """Test bank name exceeding max length"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("100.00"),
            "payment_method": "bank_transfer",
            "bank_reference": "TRANS123",
            "bank_name": "A" * 101,
        }

        serializer = PaymentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "bank_name" in serializer.errors

    def test_create_payment_notes_too_long(self):
        """Test notes exceeding max length"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("50.00"),
            "payment_method": "cash",
            "notes": "A" * 1001,
        }

        serializer = PaymentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "notes" in serializer.errors

    def test_create_payment_whitespace_trimmed(self):
        """Test whitespace trimming on string fields"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("100.00"),
            "payment_method": "bank_transfer",
            "bank_reference": "  TRANS123  ",
            "bank_name": "  Test Bank  ",
            "notes": "  Payment notes  ",
        }

        serializer = PaymentCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        assert serializer.validated_data["bank_reference"] == "TRANS123"
        assert serializer.validated_data["bank_name"] == "Test Bank"
        assert serializer.validated_data["notes"] == "Payment notes"

    def test_create_payment_large_amount(self):
        """Test creating payment with large amount"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("99999.99"),
            "payment_method": "cash",
        }

        serializer = PaymentCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_payment_minimum_amount(self):
        """Test creating payment with minimum valid amount"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("0.1"),
            "payment_method": "cash",
        }

        serializer = PaymentCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors


class OnlinePaymentIntentSerializerTest(TestCase):
    """Test cases for OnlinePaymentIntentSerializer"""

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

    def test_create_online_intent_valid_minimum(self):
        """Test creating online intent with minimum data"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("50.00"),
        }

        serializer = OnlinePaymentIntentSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_online_intent_valid_with_payment_method(self):
        """Test creating online intent with payment method ID"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("50.00"),
            "payment_method_id": "pm_test123",
            "save_payment_method": True,
        }

        serializer = OnlinePaymentIntentSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_online_intent_missing_bill_id(self):
        """Test creating online intent without bill_id"""
        data = {
            "amount": Decimal("50.00"),
        }

        serializer = OnlinePaymentIntentSerializer(data=data)
        assert not serializer.is_valid()
        assert "bill_id" in serializer.errors

    def test_create_online_intent_invalid_bill_id(self):
        """Test creating online intent with non-existent bill"""
        data = {
            "bill_id": 9999,
            "amount": Decimal("50.00"),
        }

        serializer = OnlinePaymentIntentSerializer(data=data)
        assert not serializer.is_valid()
        assert "bill_id" in serializer.errors

    def test_create_online_intent_missing_amount(self):
        """Test creating online intent without amount"""
        data = {
            "bill_id": self.bill.id,
        }

        serializer = OnlinePaymentIntentSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_create_online_intent_amount_below_minimum(self):
        """Test amount below Stripe minimum ($0.50)"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("0.49"),
        }

        serializer = OnlinePaymentIntentSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_create_online_intent_amount_at_minimum(self):
        """Test amount at Stripe minimum ($0.50)"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("0.50"),
        }

        serializer = OnlinePaymentIntentSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_online_intent_amount_exceeds_maximum(self):
        """Test amount exceeding maximum"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("100000.00"),
        }

        serializer = OnlinePaymentIntentSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_create_online_intent_invalid_payment_method_id(self):
        """Test invalid Stripe payment method ID format"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("50.00"),
            "payment_method_id": "invalid_id",
        }

        serializer = OnlinePaymentIntentSerializer(data=data)
        assert not serializer.is_valid()
        assert "payment_method_id" in serializer.errors

    def test_create_online_intent_valid_payment_method_id(self):
        """Test valid Stripe payment method ID format"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("50.00"),
            "payment_method_id": "pm_valid123456",
        }

        serializer = OnlinePaymentIntentSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_online_intent_large_amount(self):
        """Test creating online intent with large amount"""
        data = {
            "bill_id": self.bill.id,
            "amount": Decimal("99999.99"),
        }

        serializer = OnlinePaymentIntentSerializer(data=data)
        assert serializer.is_valid(), serializer.errors


class PaymentMethodSerializerTest(TestCase):
    """Test cases for PaymentMethodSerializer (read-only)"""

    def setUp(self):
        """Set up test data"""
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            user_type="patient",
        )

        self.payment_method = PaymentMethod.objects.create(
            patient=self.patient,
            method_type="card",
            stripe_payment_method_id="pm_test123",
            card_brand="visa",
            card_last4="4242",
            card_exp_month=12,
            card_exp_year=2025,
            is_default=True,
        )

    def test_serialize_payment_method_valid(self):
        """Test serializing valid payment method"""
        serializer = PaymentMethodSerializer(self.payment_method)
        data = serializer.data

        assert data["id"] == self.payment_method.id
        assert data["method_type"] == "card"
        assert data["is_default"] is True
        assert data["card_brand"] == "visa"
        assert data["card_last4"] == "4242"

    def test_payment_method_sensitive_data_hidden_for_bank_transfer(self):
        """Test that card details are hidden for bank transfers"""
        bank_method = PaymentMethod.objects.create(
            patient=self.patient,
            method_type="bank_transfer",
            bank_name="Test Bank",
            account_last4="1234",
            account_type="checking",
            card_brand="visa",  # Shouldn't display
            card_last4="4242",  # Shouldn't display
        )

        serializer = PaymentMethodSerializer(bank_method)
        data = serializer.data

        # Card details should be None
        assert data["card_brand"] is None
        assert data["card_last4"] is None

        # Bank details should be present
        assert data["bank_name"] == "Test Bank"
        assert data["account_last4"] == "1234"

    def test_payment_method_sensitive_data_hidden_for_cash(self):
        """Test that all sensitive data is hidden for cash"""
        cash_method = PaymentMethod.objects.create(
            patient=self.patient,
            method_type="cash",
        )

        serializer = PaymentMethodSerializer(cash_method)
        data = serializer.data

        # All sensitive fields should be None
        assert data["card_brand"] is None
        assert data["card_last4"] is None
        assert data["bank_name"] is None
        assert data["account_last4"] is None


class PaymentMethodCreateSerializerTest(TestCase):
    """Test cases for PaymentMethodCreateSerializer"""

    def setUp(self):
        """Set up test data"""
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            user_type="patient",
        )

    def test_create_digital_payment_method_valid(self):
        """Test creating valid digital payment method"""
        data = {
            "method_type": "card",
            "stripe_payment_method_id": "pm_test123",
            "card_brand": "visa",
            "card_last4": "4242",
            "card_exp_month": 12,
            "card_exp_year": 2025,
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_bank_transfer_method_valid(self):
        """Test creating valid bank transfer method"""
        data = {
            "method_type": "bank_transfer",
            "bank_name": "Test Bank",
            "account_last4": "1234",
            "account_type": "checking",
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_cash_method_valid(self):
        """Test creating valid cash method"""
        data = {
            "method_type": "cash",
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_digital_payment_missing_stripe_id(self):
        """Test digital payment without Stripe ID fails"""
        data = {
            "method_type": "card",
            "card_brand": "visa",
            "card_last4": "4242",
            "card_exp_month": 12,
            "card_exp_year": 2025,
            # Missing stripe_payment_method_id
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert not serializer.is_valid()

    def test_create_digital_payment_invalid_stripe_id(self):
        """Test digital payment with invalid Stripe ID format"""
        data = {
            "method_type": "card",
            "stripe_payment_method_id": "invalid_id",
            "card_brand": "visa",
            "card_last4": "4242",
            "card_exp_month": 12,
            "card_exp_year": 2025,
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "stripe_payment_method_id" in serializer.errors

    def test_create_digital_payment_missing_card_last4(self):
        """Test digital payment without card_last4"""
        data = {
            "method_type": "card",
            "stripe_payment_method_id": "pm_test123",
            "card_brand": "visa",
            # Missing card_last4
            "card_exp_month": 12,
            "card_exp_year": 2025,
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "card_fields" in serializer.errors

    def test_create_digital_payment_invalid_card_last4(self):
        """Test digital payment with invalid card_last4"""
        data = {
            "method_type": "card",
            "stripe_payment_method_id": "pm_test123",
            "card_brand": "visa",
            "card_last4": "424",  # Only 3 digits
            "card_exp_month": 12,
            "card_exp_year": 2025,
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "card_last4" in serializer.errors

    def test_create_digital_payment_invalid_exp_month(self):
        """Test digital payment with invalid expiration month"""
        data = {
            "method_type": "card",
            "stripe_payment_method_id": "pm_test123",
            "card_brand": "visa",
            "card_last4": "4242",
            "card_exp_month": 13,  # Invalid month
            "card_exp_year": 2025,
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "card_exp_month" in serializer.errors

    def test_create_digital_payment_invalid_exp_year(self):
        """Test digital payment with past expiration year"""
        data = {
            "method_type": "card",
            "stripe_payment_method_id": "pm_test123",
            "card_brand": "visa",
            "card_last4": "4242",
            "card_exp_month": 12,
            "card_exp_year": 2020,  # Past year
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "card_exp_year" in serializer.errors

    def test_create_digital_payment_with_bank_fields_fails(self):
        """Test digital payment with bank fields fails"""
        data = {
            "method_type": "card",
            "stripe_payment_method_id": "pm_test123",
            "card_brand": "visa",
            "card_last4": "4242",
            "card_exp_month": 12,
            "card_exp_year": 2025,
            "bank_name": "Test Bank",  # Should not be provided
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "bank_name" in serializer.errors

    def test_create_bank_transfer_missing_bank_name(self):
        """Test bank transfer without bank_name"""
        data = {
            "method_type": "bank_transfer",
            # Missing bank_name
            "account_last4": "1234",
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "bank_fields" in serializer.errors

    def test_create_bank_transfer_missing_account_last4(self):
        """Test bank transfer without account_last4"""
        data = {
            "method_type": "bank_transfer",
            "bank_name": "Test Bank",
            # Missing account_last4
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "bank_fields" in serializer.errors

    def test_create_bank_transfer_invalid_account_last4(self):
        """Test bank transfer with invalid account_last4"""
        data = {
            "method_type": "bank_transfer",
            "bank_name": "Test Bank",
            "account_last4": "123",  # Only 3 digits
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "account_last4" in serializer.errors

    def test_create_bank_transfer_with_card_fields_fails(self):
        """Test bank transfer with card fields fails"""
        data = {
            "method_type": "bank_transfer",
            "bank_name": "Test Bank",
            "account_last4": "1234",
            "card_brand": "visa",  # Should not be provided
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "card_brand" in serializer.errors

    def test_create_cash_method_with_payment_details_fails(self):
        """Test cash method with payment details fails"""
        data = {
            "method_type": "cash",
            "stripe_payment_method_id": "pm_test123",  # Should not be provided
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "stripe_payment_method_id" in serializer.errors

    def test_create_payment_method_set_as_default(self):
        """Test creating payment method as default"""
        data = {
            "method_type": "card",
            "stripe_payment_method_id": "pm_test123",
            "card_brand": "visa",
            "card_last4": "4242",
            "card_exp_month": 12,
            "card_exp_year": 2025,
            "is_default": True,
        }

        serializer = PaymentMethodCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
