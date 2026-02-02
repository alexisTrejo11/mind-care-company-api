from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal

User = get_user_model()


class Bill(models.Model):
    """Billing and payment information"""

    PAYMENT_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("partial", "Partial"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
        ("insurance_pending", "Insurance Pending"),
        ("insurance_approved", "Insurance Approved"),
        ("insurance_rejected", "Insurance Rejected"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("credit_card", "Credit Card"),
        ("debit_card", "Debit Card"),
        ("bank_transfer", "Bank Transfer"),
        ("insurance", "Insurance"),
        ("online", "Online Payment"),
        ("check", "Check"),
        ("wallet", "Digital Wallet"),
    ]

    INVOICE_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("viewed", "Viewed"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]

    # Basic information
    bill_number = models.CharField(max_length=20, unique=True, editable=False)
    appointment = models.OneToOneField(
        "appointments.Appointment", on_delete=models.CASCADE, related_name="bill"
    )
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bills")

    # Financial details
    subtotal = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    balance_due = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )

    # Status
    invoice_status = models.CharField(
        max_length=20, choices=INVOICE_STATUS_CHOICES, default="draft"
    )
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending"
    )

    # Payment method
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True
    )

    # Insurance information
    insurance_company = models.CharField(max_length=100, blank=True, null=True)
    policy_number = models.CharField(max_length=50, blank=True, null=True)
    insurance_claim_id = models.CharField(max_length=100, blank=True, null=True)
    insurance_coverage = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    patient_responsibility = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )

    # Dates
    invoice_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    cancellation_date = models.DateField(null=True, blank=True)

    # Notes
    notes = models.TextField(blank=True)
    terms_and_conditions = models.TextField(blank=True)

    # Stripe integration
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_invoice_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_charge_id = models.CharField(max_length=100, blank=True, null=True)

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_bills"
    )

    class Meta:
        db_table = "bills"
        verbose_name = "Bill"
        verbose_name_plural = "Bills"
        ordering = ["-invoice_date"]
        indexes = [
            models.Index(fields=["bill_number"]),
            models.Index(fields=["payment_status"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["patient", "invoice_status"]),
            models.Index(fields=["stripe_payment_intent_id"]),
        ]

    def __str__(self):
        return f"Bill #{self.bill_number} - {self.patient.get_full_name()} - ${self.total_amount}"

    def save(self, *args, **kwargs):
        """Generate bill number on creation"""
        if not self.bill_number:
            self.bill_number = self.generate_bill_number()

        # Calculate balance
        self.balance_due = max(self.total_amount - self.amount_paid, 0)

        # Update payment status
        self.update_payment_status()

        super().save(*args, **kwargs)

    def generate_bill_number(self):
        """Generate unique bill number: BILL-YYYYMM-XXXX"""
        from django.utils import timezone

        year_month = timezone.now().strftime("%Y%m")
        last_bill = (
            Bill.objects.filter(bill_number__startswith=f"BILL-{year_month}-")
            .order_by("bill_number")
            .last()
        )

        if last_bill:
            last_number = int(last_bill.bill_number.split("-")[-1])
            new_number = last_number + 1
        else:
            new_number = 1

        return f"BILL-{year_month}-{new_number:04d}"

    def update_payment_status(self):
        """Update payment status based on amounts"""
        if self.payment_status in ["cancelled", "refunded"]:
            return

        if self.amount_paid >= self.total_amount:
            self.payment_status = "paid"
            self.invoice_status = "paid"
            if not self.paid_date:
                self.paid_date = timezone.now().date()
        elif self.amount_paid > 0:
            self.payment_status = "partial"
        else:
            # Check if overdue
            if timezone.now().date() > self.due_date:
                self.payment_status = "overdue"
                self.invoice_status = "overdue"
            else:
                self.payment_status = "pending"

    def mark_as_paid(self, amount=None, payment_method=None, notes=""):
        """Mark bill as paid"""
        from django.utils import timezone

        if amount is None:
            amount = self.balance_due

        self.amount_paid += amount
        self.paid_date = timezone.now().date()

        if payment_method:
            self.payment_method = payment_method

        if notes:
            self.notes = f"{self.notes}\n\nPayment received: {notes}"

        self.update_payment_status()
        self.save()

        # Create payment record
        """
        Payment.objects.create(
            bill=self,
            amount=amount,
            payment_method=payment_method or self.payment_method,
            notes=notes,
            status="completed",
        )
        """

    def get_payment_url(self):
        """Get payment URL for online payments"""
        from django.urls import reverse
        from django.conf import settings

        if settings.DEBUG:
            base_url = "http://localhost:8000"
        else:
            base_url = settings.BASE_URL

        return f"{base_url}{reverse('billing:pay-bill', args=[self.bill_number])}"


class BillItem(models.Model):
    """Individual items on a bill"""

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=200)
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(0.01)],
    )
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    discount_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    # Calculated fields
    line_total = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, editable=False
    )
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    # Service reference
    service = models.ForeignKey(
        "specialists.Service", on_delete=models.SET_NULL, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bill_items"
        verbose_name = "Bill Item"
        verbose_name_plural = "Bill Items"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.description} - ${self.net_amount}"

    def save(self, *args, **kwargs):
        """Calculate line totals"""
        # Calculate line total
        self.line_total = self.quantity * self.unit_price

        # Calculate discount
        self.discount_amount = (self.line_total * self.discount_rate) / 100

        # Calculate taxable amount
        taxable_amount = self.line_total - self.discount_amount

        # Calculate tax
        self.tax_amount = (taxable_amount * self.tax_rate) / 100

        # Calculate net amount
        self.net_amount = taxable_amount + self.tax_amount

        super().save(*args, **kwargs)

        # Update bill totals
        if self.bill:
            self.bill.save()
