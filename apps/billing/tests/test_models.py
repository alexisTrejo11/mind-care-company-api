import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.billing.models import (
    Bill,
    BillItem,
    Payment,
    PaymentMethod,
    Refund,
    InsuranceClaim,
)
from apps.appointments.models import Appointment
from apps.users.models import User
from apps.specialists.models import Specialist


class BillModelTest(TestCase):
    """Test cases for Bill model"""

    def setUp(self):
        """Set up test data"""
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            user_type="patient",
            first_name="John",
            last_name="Doe",
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
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(minutes=60),
            duration_minutes=60,
            appointment_type="online",
            status="completed",
        )

    def test_bill_creation_valid(self):
        """Test creating a valid bill"""
        bill = Bill.objects.create(
            appointment=self.appointment,
            patient=self.patient,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("8.50"),
            total_amount=Decimal("108.50"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

        assert bill.id is not None
        assert bill.bill_number is not None
        assert bill.bill_number.startswith("BILL-")
        assert bill.invoice_status == "draft"

    def test_bill_number_auto_generation(self):
        """Test that bill number is auto-generated"""
        bill = Bill.objects.create(
            appointment=self.appointment,
            patient=self.patient,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("8.50"),
            total_amount=Decimal("108.50"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

        assert bill.bill_number is not None
        assert bill.bill_number.startswith("BILL-")

    def test_bill_amount_paid_property(self):
        """Test amount_paid property calculation"""
        bill = Bill.objects.create(
            appointment=self.appointment,
            patient=self.patient,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("8.50"),
            total_amount=Decimal("108.50"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

        # Initially no payments
        assert bill.amount_paid == Decimal("0.00")

        # Add a payment
        Payment.objects.create(
            bill=bill,
            patient=self.patient,
            amount=Decimal("50.00"),
            payment_method="cash",
            status="completed",
        )

        bill.refresh_from_db()
        assert bill.amount_paid == Decimal("50.00")

    def test_bill_balance_due_property(self):
        """Test balance_due property calculation"""
        bill = Bill.objects.create(
            appointment=self.appointment,
            patient=self.patient,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("8.50"),
            total_amount=Decimal("108.50"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

        # Initially full balance
        assert bill.balance_due == Decimal("108.50")

        # Add partial payment
        Payment.objects.create(
            bill=bill,
            patient=self.patient,
            amount=Decimal("50.00"),
            payment_method="cash",
            status="completed",
        )

        bill.refresh_from_db()
        assert bill.balance_due == Decimal("58.50")

    def test_bill_payment_status_pending(self):
        """Test payment_status property when pending"""
        bill = Bill.objects.create(
            appointment=self.appointment,
            patient=self.patient,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("8.50"),
            total_amount=Decimal("108.50"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

        assert bill.payment_status == "pending"

    def test_bill_payment_status_partial(self):
        """Test payment_status property when partially paid"""
        bill = Bill.objects.create(
            appointment=self.appointment,
            patient=self.patient,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("8.50"),
            total_amount=Decimal("108.50"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

        Payment.objects.create(
            bill=bill,
            patient=self.patient,
            amount=Decimal("50.00"),
            payment_method="cash",
            status="completed",
        )

        bill.refresh_from_db()
        assert bill.payment_status == "partial"

    def test_bill_payment_status_paid(self):
        """Test payment_status property when fully paid"""
        bill = Bill.objects.create(
            appointment=self.appointment,
            patient=self.patient,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("8.50"),
            total_amount=Decimal("108.50"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

        Payment.objects.create(
            bill=bill,
            patient=self.patient,
            amount=Decimal("108.50"),
            payment_method="cash",
            status="completed",
        )

        bill.refresh_from_db()
        assert bill.payment_status == "paid"
        assert bill.invoice_status == "paid"

    def test_bill_payment_status_cancelled(self):
        """Test payment_status property when bill is cancelled"""
        bill = Bill.objects.create(
            appointment=self.appointment,
            patient=self.patient,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("8.50"),
            total_amount=Decimal("108.50"),
            invoice_status="cancelled",
            due_date=timezone.now().date() + timedelta(days=14),
        )

        assert bill.payment_status == "cancelled"

    def test_bill_with_insurance_information(self):
        """Test bill with insurance details"""
        bill = Bill.objects.create(
            appointment=self.appointment,
            patient=self.patient,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("8.50"),
            total_amount=Decimal("108.50"),
            insurance_company="Blue Cross",
            policy_number="BC123456",
            insurance_coverage=Decimal("80.00"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

        assert bill.insurance_company == "Blue Cross"
        assert bill.policy_number == "BC123456"
        assert bill.insurance_coverage == Decimal("80.00")

    def test_bill_with_notes(self):
        """Test bill with notes"""
        notes = "Please send invoice to billing department"
        bill = Bill.objects.create(
            appointment=self.appointment,
            patient=self.patient,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("8.50"),
            total_amount=Decimal("108.50"),
            notes=notes,
            due_date=timezone.now().date() + timedelta(days=14),
        )

        assert bill.notes == notes

    def test_bill_unique_bill_number(self):
        """Test that bill numbers are unique"""
        bill1 = Bill.objects.create(
            appointment=self.appointment,
            patient=self.patient,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("8.50"),
            total_amount=Decimal("108.50"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

        appointment2 = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_date=timezone.now().date() + timedelta(days=2),
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(minutes=60),
            duration_minutes=60,
            appointment_type="online",
            status="completed",
        )

        bill2 = Bill.objects.create(
            appointment=appointment2,
            patient=self.patient,
            subtotal=Decimal("150.00"),
            tax_amount=Decimal("12.75"),
            total_amount=Decimal("162.75"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

        assert bill1.bill_number != bill2.bill_number


class BillItemModelTest(TestCase):
    """Test cases for BillItem model"""

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
            total_amount=Decimal("108.50"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

    def test_bill_item_creation_valid(self):
        """Test creating a valid bill item"""
        item = BillItem.objects.create(
            bill=self.bill,
            description="Consultation Service",
            quantity=Decimal("1.00"),
            unit_price=Decimal("100.00"),
            tax_rate=Decimal("8.5"),
        )

        assert item.id is not None
        assert item.description == "Consultation Service"
        assert item.line_total == Decimal("100.00")

    def test_bill_item_calculation(self):
        """Test bill item calculations"""
        item = BillItem.objects.create(
            bill=self.bill,
            description="Service",
            quantity=Decimal("2.00"),
            unit_price=Decimal("50.00"),
            tax_rate=Decimal("10.0"),
            discount_rate=Decimal("20.0"),
        )

        # line_total = 2 * 50 = 100
        assert item.line_total == Decimal("100.00")

        # discount_amount = 100 * 20 / 100 = 20
        assert item.discount_amount == Decimal("20.00")

        # taxable_amount = 100 - 20 = 80
        # tax_amount = 80 * 10 / 100 = 8
        assert item.tax_amount == Decimal("8.00")

        # net_amount = 80 + 8 = 88
        assert item.net_amount == Decimal("88.00")

    def test_bill_item_with_zero_discount(self):
        """Test bill item with no discount"""
        item = BillItem.objects.create(
            bill=self.bill,
            description="Service",
            quantity=Decimal("1.00"),
            unit_price=Decimal("100.00"),
            tax_rate=Decimal("8.5"),
            discount_rate=Decimal("0.0"),
        )

        assert item.discount_amount == Decimal("0.00")
        assert item.tax_amount == Decimal("8.50")
        assert item.net_amount == Decimal("108.50")

    def test_bill_item_with_zero_tax(self):
        """Test bill item with no tax"""
        item = BillItem.objects.create(
            bill=self.bill,
            description="Service",
            quantity=Decimal("1.00"),
            unit_price=Decimal("100.00"),
            tax_rate=Decimal("0.0"),
        )

        assert item.tax_amount == Decimal("0.00")
        assert item.net_amount == Decimal("100.00")


class PaymentModelTest(TestCase):
    """Test cases for Payment model"""

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
            total_amount=Decimal("108.50"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

    def test_payment_creation_valid(self):
        """Test creating a valid payment"""
        payment = Payment.objects.create(
            bill=self.bill,
            patient=self.patient,
            amount=Decimal("108.50"),
            payment_method="cash",
            status="completed",
        )

        assert payment.id is not None
        assert payment.payment_number is not None
        assert payment.payment_number.startswith("PAY-")
        assert payment.status == "completed"

    def test_payment_number_auto_generation(self):
        """Test that payment number is auto-generated"""
        payment = Payment.objects.create(
            bill=self.bill,
            patient=self.patient,
            amount=Decimal("50.00"),
            payment_method="cash",
        )

        assert payment.payment_number is not None
        assert payment.payment_number.startswith("PAY-")

    def test_payment_cash_auto_reference(self):
        """Test that cash payments get auto-generated reference"""
        payment = Payment.objects.create(
            bill=self.bill,
            patient=self.patient,
            amount=Decimal("50.00"),
            payment_method="cash",
        )

        assert payment.bank_reference is not None
        assert payment.bank_reference.startswith("CASH-")

    def test_payment_mark_as_completed(self):
        """Test marking payment as completed"""
        payment = Payment.objects.create(
            bill=self.bill,
            patient=self.patient,
            amount=Decimal("50.00"),
            payment_method="cash",
            status="pending",
        )

        payment.mark_as_completed()

        assert payment.status == "completed"
        assert payment.processed_at is not None

    def test_payment_mark_as_failed(self):
        """Test marking payment as failed"""
        payment = Payment.objects.create(
            bill=self.bill,
            patient=self.patient,
            amount=Decimal("50.00"),
            payment_method="cash",
            status="pending",
        )

        payment.mark_as_failed("Card declined")

        assert payment.status == "failed"
        assert "Card declined" in payment.admin_notes

    def test_payment_refund(self):
        """Test refunding a payment"""
        payment = Payment.objects.create(
            bill=self.bill,
            patient=self.patient,
            amount=Decimal("108.50"),
            payment_method="cash",
            status="completed",
        )

        payment.refund()

        assert payment.status == "refunded"
        assert payment.refunded_at is not None

    def test_payment_with_bank_details(self):
        """Test payment with bank transfer details"""
        payment = Payment.objects.create(
            bill=self.bill,
            patient=self.patient,
            amount=Decimal("100.00"),
            payment_method="bank_transfer",
            bank_reference="TRANS123456",
            bank_name="Test Bank",
            status="completed",
        )

        assert payment.bank_reference == "TRANS123456"
        assert payment.bank_name == "Test Bank"

    def test_payment_with_card_details(self):
        """Test payment with card details"""
        payment = Payment.objects.create(
            bill=self.bill,
            patient=self.patient,
            amount=Decimal("100.00"),
            payment_method="credit_card",
            card_brand="visa",
            card_last4="4242",
            card_exp_month=12,
            card_exp_year=2025,
            status="completed",
        )

        assert payment.card_brand == "visa"
        assert payment.card_last4 == "4242"


class PaymentMethodModelTest(TestCase):
    """Test cases for PaymentMethod model"""

    def setUp(self):
        """Set up test data"""
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            user_type="patient",
        )

    def test_payment_method_card_creation(self):
        """Test creating a card payment method"""
        method = PaymentMethod.objects.create(
            patient=self.patient,
            method_type="card",
            stripe_payment_method_id="pm_test123",
            card_brand="visa",
            card_last4="4242",
            card_exp_month=12,
            card_exp_year=2025,
        )

        assert method.id is not None
        assert method.method_type == "card"
        assert method.card_brand == "visa"

    def test_payment_method_bank_transfer_creation(self):
        """Test creating a bank transfer payment method"""
        method = PaymentMethod.objects.create(
            patient=self.patient,
            method_type="bank_transfer",
            bank_name="Test Bank",
            account_last4="1234",
            account_type="checking",
        )

        assert method.method_type == "bank_transfer"
        assert method.bank_name == "Test Bank"

    def test_payment_method_cash_creation(self):
        """Test creating a cash payment method"""
        method = PaymentMethod.objects.create(
            patient=self.patient,
            method_type="cash",
        )

        assert method.method_type == "cash"

    def test_payment_method_set_default(self):
        """Test setting payment method as default"""
        method1 = PaymentMethod.objects.create(
            patient=self.patient,
            method_type="card",
            stripe_payment_method_id="pm_test1",
            card_brand="visa",
            card_last4="4242",
            card_exp_month=12,
            card_exp_year=2025,
            is_default=True,
        )

        method2 = PaymentMethod.objects.create(
            patient=self.patient,
            method_type="card",
            stripe_payment_method_id="pm_test2",
            card_brand="mastercard",
            card_last4="5555",
            card_exp_month=6,
            card_exp_year=2026,
            is_default=True,
        )

        # When method2 is set as default, method1 should no longer be default
        method1.refresh_from_db()
        assert method1.is_default == False
        assert method2.is_default == True

    def test_payment_method_mark_as_used(self):
        """Test marking payment method as used"""
        method = PaymentMethod.objects.create(
            patient=self.patient,
            method_type="card",
            stripe_payment_method_id="pm_test123",
            card_brand="visa",
            card_last4="4242",
            card_exp_month=12,
            card_exp_year=2025,
        )

        assert method.last_used is None

        method.mark_as_used()

        assert method.last_used is not None

    def test_payment_method_requires_stripe_property(self):
        """Test requires_stripe property"""
        card_method = PaymentMethod.objects.create(
            patient=self.patient,
            method_type="card",
            stripe_payment_method_id="pm_test123",
            card_brand="visa",
            card_last4="4242",
            card_exp_month=12,
            card_exp_year=2025,
        )

        cash_method = PaymentMethod.objects.create(
            patient=self.patient,
            method_type="cash",
        )

        assert card_method.requires_stripe == True
        assert cash_method.requires_stripe == False

    def test_payment_method_is_expired_property(self):
        """Test is_expired property"""
        # Create expired card
        expired_method = PaymentMethod.objects.create(
            patient=self.patient,
            method_type="card",
            stripe_payment_method_id="pm_expired",
            card_brand="visa",
            card_last4="4242",
            card_exp_month=1,
            card_exp_year=2020,
        )

        # Create valid card
        valid_method = PaymentMethod.objects.create(
            patient=self.patient,
            method_type="card",
            stripe_payment_method_id="pm_valid",
            card_brand="visa",
            card_last4="5555",
            card_exp_month=12,
            card_exp_year=2030,
        )

        assert expired_method.is_expired == True
        assert valid_method.is_expired == False


class RefundModelTest(TestCase):
    """Test cases for Refund model"""

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

    def test_refund_creation_valid(self):
        """Test creating a valid refund"""
        refund = Refund.objects.create(
            payment=self.payment,
            bill=self.bill,
            amount=Decimal("50.00"),
            reason="requested_by_customer",
        )

        assert refund.id is not None
        assert refund.refund_number is not None
        assert refund.refund_number.startswith("REF-")
        assert refund.status == "requested"

    def test_refund_number_auto_generation(self):
        """Test that refund number is auto-generated"""
        refund = Refund.objects.create(
            payment=self.payment,
            bill=self.bill,
            amount=Decimal("50.00"),
            reason="requested_by_customer",
        )

        assert refund.refund_number is not None
        assert refund.refund_number.startswith("REF-")

    def test_refund_mark_as_completed(self):
        """Test marking refund as completed"""
        refund = Refund.objects.create(
            payment=self.payment,
            bill=self.bill,
            amount=Decimal("50.00"),
            reason="requested_by_customer",
            status="processing",
        )

        refund.mark_as_completed()

        assert refund.status == "completed"
        assert refund.processed_date is not None

    def test_refund_with_reason_details(self):
        """Test refund with reason details"""
        refund = Refund.objects.create(
            payment=self.payment,
            bill=self.bill,
            amount=Decimal("50.00"),
            reason="other",
            reason_details="Patient requested partial refund due to service issues",
        )

        assert refund.reason == "other"
        assert "service issues" in refund.reason_details


class InsuranceClaimModelTest(TestCase):
    """Test cases for InsuranceClaim model"""

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
            total_amount=Decimal("108.50"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

    def test_insurance_claim_creation_valid(self):
        """Test creating a valid insurance claim"""
        claim = InsuranceClaim.objects.create(
            bill=self.bill,
            patient=self.patient,
            claim_number="CLAIM123456",
            insurance_company="Blue Cross",
            policy_number="BC123456",
            subscriber_name="John Doe",
            subscriber_relationship="self",
            date_of_service=timezone.now().date(),
            total_claimed_amount=Decimal("108.50"),
        )

        assert claim.id is not None
        assert claim.claim_number == "CLAIM123456"
        assert claim.status == "draft"

    def test_insurance_claim_with_diagnosis_codes(self):
        """Test insurance claim with diagnosis codes"""
        codes = ["A00.0", "B01.1"]
        claim = InsuranceClaim.objects.create(
            bill=self.bill,
            patient=self.patient,
            claim_number="CLAIM123456",
            insurance_company="Blue Cross",
            policy_number="BC123456",
            subscriber_name="John Doe",
            subscriber_relationship="self",
            date_of_service=timezone.now().date(),
            total_claimed_amount=Decimal("108.50"),
            diagnosis_codes=codes,
        )

        assert claim.diagnosis_codes == codes

    def test_insurance_claim_with_procedure_codes(self):
        """Test insurance claim with procedure codes"""
        codes = ["99213", "99214"]
        claim = InsuranceClaim.objects.create(
            bill=self.bill,
            patient=self.patient,
            claim_number="CLAIM123456",
            insurance_company="Blue Cross",
            policy_number="BC123456",
            subscriber_name="John Doe",
            subscriber_relationship="self",
            date_of_service=timezone.now().date(),
            total_claimed_amount=Decimal("108.50"),
            procedure_codes=codes,
        )

        assert claim.procedure_codes == codes

    def test_insurance_claim_with_amounts(self):
        """Test insurance claim with responsibility amounts"""
        claim = InsuranceClaim.objects.create(
            bill=self.bill,
            patient=self.patient,
            claim_number="CLAIM123456",
            insurance_company="Blue Cross",
            policy_number="BC123456",
            subscriber_name="John Doe",
            subscriber_relationship="self",
            date_of_service=timezone.now().date(),
            total_claimed_amount=Decimal("100.00"),
            insurance_responsibility=Decimal("80.00"),
            patient_responsibility=Decimal("20.00"),
        )

        assert claim.total_claimed_amount == Decimal("100.00")
        assert claim.insurance_responsibility == Decimal("80.00")
        assert claim.patient_responsibility == Decimal("20.00")

    def test_insurance_claim_status_progression(self):
        """Test insurance claim status progression"""
        claim = InsuranceClaim.objects.create(
            bill=self.bill,
            patient=self.patient,
            claim_number="CLAIM123456",
            insurance_company="Blue Cross",
            policy_number="BC123456",
            subscriber_name="John Doe",
            subscriber_relationship="self",
            date_of_service=timezone.now().date(),
            total_claimed_amount=Decimal("108.50"),
        )

        assert claim.status == "draft"

        claim.status = "submitted"
        claim.date_submitted = timezone.now().date()
        claim.save()

        claim.refresh_from_db()
        assert claim.status == "submitted"
        assert claim.date_submitted is not None

    def test_insurance_claim_denial_reason(self):
        """Test insurance claim with denial reason"""
        claim = InsuranceClaim.objects.create(
            bill=self.bill,
            patient=self.patient,
            claim_number="CLAIM123456",
            insurance_company="Blue Cross",
            policy_number="BC123456",
            subscriber_name="John Doe",
            subscriber_relationship="self",
            date_of_service=timezone.now().date(),
            total_claimed_amount=Decimal("108.50"),
            status="denied",
            denial_reason="Service not covered under plan",
        )

        assert claim.status == "denied"
        assert "not covered" in claim.denial_reason
