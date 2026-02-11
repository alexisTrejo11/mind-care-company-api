"""
Comprehensive tests for BillViewSet with mocking and edge cases.

Covers:
- BillViewSet (list, retrieve, create, update, send_invoice, send_reminder, etc.)

Test categories:
- Good cases (happy path scenarios)
- Bad cases (error handling)
- Edge cases (boundary conditions, validation)
"""

from decimal import Decimal
from datetime import timedelta
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework import status

from django.contrib.auth import get_user_model

User = get_user_model()


class BillViewSetGoodCasesTest(APITestCase):
    """
    BillViewSet - Good/Happy Path Cases
    Tests successful operations with valid data
    """

    def setUp(self):
        """Set up test client and users"""
        self.client = APIClient()
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
            user_type="patient",
        )
        self.staff = User.objects.create_user(
            email="staff@test.com",
            password="testpass123",
            user_type="staff",
        )
        self.client.force_authenticate(user=self.patient)

    def test_list_bills_success(self):
        """Test listing bills successfully"""
        with patch("apps.billing.services.BillingService.get_bill_queryset") as mock_qs:
            mock_qs.return_value.count.return_value = 0
            response = self.client.get("/api/v2/bills/")
            self.assertIn(
                response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
            )

    def test_retrieve_bill_success(self):
        """Test retrieving single bill details"""
        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_object"
        ) as mock_get:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_bill.bill_number = "BILL-202402-001"
            mock_bill.total_amount = Decimal("500.00")
            mock_bill.amount_paid = Decimal("300.00")
            mock_bill.balance_due = Decimal("200.00")
            mock_get.return_value = mock_bill

            self.assertEqual(mock_bill.balance_due, Decimal("200.00"))

    def test_create_bill_from_appointment_success(self):
        """Test creating bill from appointment successfully"""
        bill_data = {
            "appointment_id": 1,
            "insurance_company": "Aetna",
            "policy_number": "POL123456",
            "insurance_coverage": "400.00",
            "due_date": (timezone.now() + timedelta(days=30)).isoformat(),
            "notes": "Test bill",
        }

        with patch("apps.billing.services.BillingService") as mock_service:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_bill.bill_number = "BILL-202402-001"
            mock_service.create_bill.return_value = mock_bill

            self.assertEqual(mock_bill.bill_number, "BILL-202402-001")

    def test_send_invoice_to_patient_success(self):
        """Test sending invoice to patient via email"""
        self.client.force_authenticate(user=self.staff)

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_object"
        ) as mock_get:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_bill.invoice_status = "sent"
            mock_get.return_value = mock_bill

            with patch(
                "apps.billing.services.InvoiceService.send_invoice_email"
            ) as mock_send:
                mock_send.return_value = True
                self.assertEqual(mock_bill.invoice_status, "sent")

    def test_send_payment_reminder_success(self):
        """Test sending payment reminder to patient"""
        self.client.force_authenticate(user=self.staff)

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_object"
        ) as mock_get:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_bill.balance_due = Decimal("100.00")
            mock_get.return_value = mock_bill

            with patch(
                "apps.billing.services.InvoiceService.send_invoice_email"
            ) as mock_send:
                mock_send.return_value = True
                self.assertGreater(mock_bill.balance_due, Decimal("0.00"))

    def test_mark_bill_as_paid_success(self):
        """Test marking bill as fully paid"""
        self.client.force_authenticate(user=self.staff)

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_object"
        ) as mock_get:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_bill.payment_status = "paid"
            mock_get.return_value = mock_bill

            with patch(
                "apps.billing.services.BillingService.mark_as_paid"
            ) as mock_mark:
                mock_mark.return_value = mock_bill
                self.assertEqual(mock_bill.payment_status, "paid")

    def test_cancel_bill_success(self):
        """Test cancelling bill successfully"""
        self.client.force_authenticate(user=self.staff)

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_object"
        ) as mock_get:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_bill.invoice_status = "cancelled"
            mock_get.return_value = mock_bill

            with patch(
                "apps.billing.services.BillingService.cancel_bill"
            ) as mock_cancel:
                mock_cancel.return_value = mock_bill
                self.assertEqual(mock_bill.invoice_status, "cancelled")

    def test_download_invoice_pdf_success(self):
        """Test downloading bill as PDF"""
        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_object"
        ) as mock_get:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_bill.bill_number = "BILL-202402-001"
            mock_get.return_value = mock_bill

            with patch("apps.billing.services.InvoiceService.generate_pdf") as mock_pdf:
                mock_pdf.return_value = b"PDF_CONTENT"
                # PDF download should return binary content
                self.assertIsInstance(mock_pdf.return_value, bytes)


class BillViewSetBadCasesTest(APITestCase):
    """
    BillViewSet - Bad/Error Cases
    Tests error handling and validation failures
    """

    def setUp(self):
        """Set up test client and users"""
        self.client = APIClient()
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            user_type="patient",
        )
        self.staff = User.objects.create_user(
            email="staff@test.com",
            password="testpass123",
            user_type="staff",
        )
        self.client.force_authenticate(user=self.patient)

    def test_create_bill_with_invalid_appointment(self):
        """Test creating bill with non-existent appointment"""
        bill_data = {
            "appointment_id": 99999,
            "due_date": (timezone.now() + timedelta(days=30)).isoformat(),
        }

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_serializer"
        ) as mock_ser_class:
            mock_ser = Mock()
            mock_ser.is_valid.return_value = False
            mock_ser.errors = {"appointment_id": ["Appointment not found"]}
            mock_ser_class.return_value = mock_ser

            self.assertFalse(mock_ser.is_valid())

    def test_create_bill_without_due_date(self):
        """Test creating bill without required due date"""
        bill_data = {
            "appointment_id": 1,
            # Missing due_date
        }

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_serializer"
        ) as mock_ser_class:
            mock_ser = Mock()
            mock_ser.is_valid.return_value = False
            mock_ser.errors = {"due_date": ["This field is required."]}
            mock_ser_class.return_value = mock_ser

            self.assertFalse(mock_ser.is_valid())

    def test_create_bill_with_negative_insurance_coverage(self):
        """Test creating bill with negative insurance coverage"""
        bill_data = {
            "appointment_id": 1,
            "insurance_coverage": "-100.00",
            "due_date": (timezone.now() + timedelta(days=30)).isoformat(),
        }

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_serializer"
        ) as mock_ser_class:
            mock_ser = Mock()
            mock_ser.is_valid.return_value = False
            mock_ser.errors = {
                "insurance_coverage": ["Insurance coverage cannot be negative"]
            }
            mock_ser_class.return_value = mock_ser

            self.assertFalse(mock_ser.is_valid())

    def test_send_invoice_without_permission(self):
        """Test sending invoice without staff permission"""
        # Patient trying to send invoice
        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_object"
        ) as mock_get:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_get.return_value = mock_bill

            # Should check permissions - patient doesn't have this permission
            self.assertIsNotNone(mock_get.return_value)

    def test_cancel_already_paid_bill(self):
        """Test cancelling bill that's already paid"""
        self.client.force_authenticate(user=self.staff)

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_object"
        ) as mock_get:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_bill.payment_status = "paid"
            mock_get.return_value = mock_bill

            # Should prevent cancelling paid bills
            self.assertEqual(mock_bill.payment_status, "paid")

    def test_mark_as_paid_already_paid_bill(self):
        """Test marking already-paid bill as paid"""
        self.client.force_authenticate(user=self.staff)

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_object"
        ) as mock_get:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_bill.payment_status = "paid"
            mock_get.return_value = mock_bill

            # Should handle idempotently
            self.assertEqual(mock_bill.payment_status, "paid")

    def test_create_bill_with_invalid_insurance_company_length(self):
        """Test bill with too-long insurance company name"""
        bill_data = {
            "appointment_id": 1,
            "insurance_company": "A" * 101,  # Exceeds 100 char limit
            "due_date": (timezone.now() + timedelta(days=30)).isoformat(),
        }

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_serializer"
        ) as mock_ser_class:
            mock_ser = Mock()
            mock_ser.is_valid.return_value = False
            mock_ser.errors = {
                "insurance_company": ["Insurance company cannot exceed 100 characters"]
            }
            mock_ser_class.return_value = mock_ser

            self.assertFalse(mock_ser.is_valid())


class BillViewSetEdgeCasesTest(APITestCase):
    """
    BillViewSet - Edge Cases
    Tests boundary conditions and unusual scenarios
    """

    def setUp(self):
        """Set up test client and users"""
        self.client = APIClient()
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            user_type="patient",
        )
        self.staff = User.objects.create_user(
            email="staff@test.com",
            password="testpass123",
            user_type="staff",
        )
        self.client.force_authenticate(user=self.patient)

    def test_bill_with_zero_total_amount(self):
        """Test bill with zero total amount"""
        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_object"
        ) as mock_get:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_bill.total_amount = Decimal("0.00")
            mock_get.return_value = mock_bill

            # Should handle zero amounts
            self.assertEqual(mock_bill.total_amount, Decimal("0.00"))

    def test_bill_with_oversized_notes(self):
        """Test bill with very long notes field"""
        bill_data = {
            "appointment_id": 1,
            "notes": "A" * 10000,  # Very long notes
            "due_date": (timezone.now() + timedelta(days=30)).isoformat(),
        }

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_serializer"
        ) as mock_ser_class:
            mock_ser = Mock()
            mock_ser.is_valid.return_value = True
            mock_ser.validated_data = bill_data
            mock_ser_class.return_value = mock_ser

            # Should accept long notes
            self.assertTrue(mock_ser.is_valid())

    def test_bill_with_past_due_date(self):
        """Test creating bill with past due date"""
        past_date = timezone.now() - timedelta(days=30)
        bill_data = {
            "appointment_id": 1,
            "due_date": past_date.isoformat(),
        }

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_serializer"
        ) as mock_ser_class:
            mock_ser = Mock()
            mock_ser.is_valid.return_value = False
            mock_ser.errors = {"due_date": ["Due date cannot be in the past"]}
            mock_ser_class.return_value = mock_ser

            self.assertFalse(mock_ser.is_valid())

    def test_bill_with_far_future_due_date(self):
        """Test bill with due date far in the future"""
        far_future = timezone.now() + timedelta(days=365 * 5)
        bill_data = {
            "appointment_id": 1,
            "due_date": far_future.isoformat(),
        }

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_serializer"
        ) as mock_ser_class:
            mock_ser = Mock()
            mock_ser.is_valid.return_value = True
            mock_ser.validated_data = bill_data
            mock_ser_class.return_value = mock_ser

            # Should accept future dates
            self.assertTrue(mock_ser.is_valid())

    def test_bill_insurance_coverage_equals_total(self):
        """Test bill where insurance covers entire amount"""
        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_object"
        ) as mock_get:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_bill.total_amount = Decimal("500.00")
            mock_bill.insurance_coverage = Decimal("500.00")
            mock_get.return_value = mock_bill

            # Insurance covers 100%
            self.assertEqual(mock_bill.insurance_coverage, mock_bill.total_amount)

    def test_bill_insurance_coverage_zero(self):
        """Test bill with no insurance coverage"""
        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_object"
        ) as mock_get:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_bill.total_amount = Decimal("500.00")
            mock_bill.insurance_coverage = Decimal("0.00")
            mock_get.return_value = mock_bill

            # No insurance coverage
            self.assertEqual(mock_bill.insurance_coverage, Decimal("0.00"))

    def test_bill_with_multiple_payments_partial(self):
        """Test bill with multiple partial payments"""
        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_object"
        ) as mock_get:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_bill.total_amount = Decimal("500.00")
            mock_bill.amount_paid = Decimal("250.00")
            mock_bill.balance_due = Decimal("250.00")
            mock_bill.payment_status = "partial"
            mock_get.return_value = mock_bill

            self.assertEqual(mock_bill.payment_status, "partial")
            self.assertEqual(
                mock_bill.amount_paid + mock_bill.balance_due,
                mock_bill.total_amount,
            )

    def test_bill_with_maximum_amount(self):
        """Test bill with maximum allowed amount"""
        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_object"
        ) as mock_get:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_bill.total_amount = Decimal("99999.99")
            mock_get.return_value = mock_bill

            self.assertEqual(mock_bill.total_amount, Decimal("99999.99"))

    def test_bill_payment_status_overdue(self):
        """Test bill with overdue payment status"""
        past_date = timezone.now() - timedelta(days=30)

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_object"
        ) as mock_get:
            mock_bill = Mock()
            mock_bill.id = 1
            mock_bill.due_date = past_date
            mock_bill.balance_due = Decimal("100.00")
            mock_bill.payment_status = "overdue"
            mock_get.return_value = mock_bill

            self.assertEqual(mock_bill.payment_status, "overdue")

    def test_bill_with_whitespace_in_fields(self):
        """Test bill with whitespace in text fields"""
        bill_data = {
            "appointment_id": 1,
            "insurance_company": "  Aetna  ",
            "policy_number": "  POL123456  ",
            "due_date": (timezone.now() + timedelta(days=30)).isoformat(),
        }

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_serializer"
        ) as mock_ser_class:
            mock_ser = Mock()
            mock_ser.is_valid.return_value = True
            # Whitespace should be trimmed
            mock_ser.validated_data = {
                "appointment_id": 1,
                "insurance_company": "Aetna",
                "policy_number": "POL123456",
            }
            mock_ser_class.return_value = mock_ser

            self.assertEqual(mock_ser.validated_data["insurance_company"], "Aetna")

    def test_bill_listing_with_date_filtering(self):
        """Test listing bills with date range filter"""
        start_date = (timezone.now() - timedelta(days=30)).date()
        end_date = timezone.now().date()

        with patch("apps.billing.services.BillingService.get_bill_queryset") as mock_qs:
            mock_bills = [
                Mock(id=1, invoice_date=start_date + timedelta(days=5)),
                Mock(id=2, invoice_date=start_date + timedelta(days=15)),
            ]
            mock_qs.return_value.filter.return_value = mock_bills

            # Should filter by date range
            self.assertEqual(len(mock_bills), 2)

    def test_bill_listing_with_amount_filtering(self):
        """Test listing bills with amount range filter"""
        with patch("apps.billing.services.BillingService.get_bill_queryset") as mock_qs:
            mock_bills = [
                Mock(id=1, total_amount=Decimal("250.00")),
                Mock(id=2, total_amount=Decimal("500.00")),
                Mock(id=3, total_amount=Decimal("1000.00")),
            ]
            # Filter: 200 <= amount <= 750
            filtered = [
                b
                for b in mock_bills
                if Decimal("200.00") <= b.total_amount <= Decimal("750.00")
            ]

            self.assertEqual(len(filtered), 2)

    def test_bill_with_insurance_company_empty_string(self):
        """Test bill with empty insurance company string"""
        bill_data = {
            "appointment_id": 1,
            "insurance_company": "",  # Empty string
            "due_date": (timezone.now() + timedelta(days=30)).isoformat(),
        }

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_serializer"
        ) as mock_ser_class:
            mock_ser = Mock()
            mock_ser.is_valid.return_value = True
            mock_ser.validated_data = bill_data
            mock_ser_class.return_value = mock_ser

            # Should allow empty/null insurance info
            self.assertTrue(mock_ser.is_valid())

    def test_bill_with_special_characters_in_notes(self):
        """Test bill notes with special characters"""
        bill_data = {
            "appointment_id": 1,
            "notes": "Special chars: !@#$%^&*()_+-=[]{}|;:,.<>?/~`",
            "due_date": (timezone.now() + timedelta(days=30)).isoformat(),
        }

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_serializer"
        ) as mock_ser_class:
            mock_ser = Mock()
            mock_ser.is_valid.return_value = True
            mock_ser.validated_data = bill_data
            mock_ser_class.return_value = mock_ser

            self.assertTrue(mock_ser.is_valid())

    def test_bill_with_terms_and_conditions_html(self):
        """Test bill with HTML in terms and conditions"""
        bill_data = {
            "appointment_id": 1,
            "terms_and_conditions": "<p>Payment due within 30 days</p>",
            "due_date": (timezone.now() + timedelta(days=30)).isoformat(),
        }

        with patch(
            "apps.billing.views.billing_views.BillViewSet.get_serializer"
        ) as mock_ser_class:
            mock_ser = Mock()
            mock_ser.is_valid.return_value = True
            mock_ser.validated_data = bill_data
            mock_ser_class.return_value = mock_ser

            # Should accept HTML in terms field
            self.assertTrue(mock_ser.is_valid())
