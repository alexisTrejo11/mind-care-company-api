from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal

User = get_user_model()


class Bill(models.Model):
    """Billing and payment information"""

    INVOICE_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("viewed", "Viewed"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]

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
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    invoice_status = models.CharField(
        max_length=20, choices=INVOICE_STATUS_CHOICES, default="draft"
    )

    # Insurance (if applicable)
    insurance_company = models.CharField(max_length=100, blank=True, null=True)
    policy_number = models.CharField(max_length=50, blank=True, null=True)
    insurance_coverage = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )

    # Payment tracking fields
    stripe_invoice_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)

    # Dates
    cancellation_date = models.DateField(null=True, blank=True)
    invoice_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)  # Added back for tracking

    # Notes
    notes = models.TextField(blank=True)
    terms_and_conditions = models.TextField(blank=True)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_bills"
    )

    @property
    def amount_paid(self):
        """Total paid so far (calculated from payments)"""
        paid_amount = self.payments.filter(status="completed").aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0.00")

        # Subtract refunded amounts
        refunded_amount = self.payments.filter(status="refunded").aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0.00")

        return paid_amount - refunded_amount

    @property
    def balance_due(self):
        """Balance due (calculated from total amount and payments)"""
        return max(self.total_amount - self.amount_paid, Decimal("0.00"))

    @property
    def payment_status(self):
        """Payment status based on actual payments and invoice status"""
        if self.invoice_status == "cancelled":
            return "cancelled"

        paid = self.amount_paid

        if paid >= self.total_amount:
            # Update invoice status to paid if not already
            if self.invoice_status != "paid":
                self.invoice_status = "paid"
                self.paid_date = timezone.now().date()
                self.save(update_fields=["invoice_status", "paid_date"])
            return "paid"
        elif paid > 0:
            return "partial"
        elif timezone.now().date() > self.due_date:
            # Update invoice status to overdue if not already
            if self.invoice_status not in ["paid", "cancelled"]:
                self.invoice_status = "overdue"
                self.save(update_fields=["invoice_status"])
            return "overdue"
        else:
            return "pending"

    class Meta:
        db_table = "bills"
        verbose_name = "Bill"
        verbose_name_plural = "Bills"
        ordering = ["-invoice_date"]
        indexes = [
            models.Index(fields=["bill_number"]),
            models.Index(fields=["invoice_status"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["patient", "invoice_status"]),
            models.Index(fields=["stripe_invoice_id"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Bill #{self.bill_number} - {self.patient.get_full_name()} - ${self.total_amount}"

    def save(self, *args, **kwargs):
        """Generate bill number on creation"""
        if not self.bill_number:
            self.bill_number = self.generate_bill_number()

        # Calculate balance and update status if needed
        if not self._state.adding:  # Only on updates
            self.update_status_if_needed()

        super().save(*args, **kwargs)

    def generate_bill_number(self):
        """Generate unique bill number: BILL-YYYYMM-XXXX"""
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

    def update_status_if_needed(self):
        """Update invoice status based on payments"""
        paid = self.amount_paid

        if paid >= self.total_amount and self.invoice_status != "paid":
            self.invoice_status = "paid"
            self.paid_date = timezone.now().date()
        elif paid > 0 and self.invoice_status not in ["paid", "cancelled"]:
            self.invoice_status = "sent"  # Partial payment, invoice still active
        elif timezone.now().date() > self.due_date and self.invoice_status not in [
            "paid",
            "cancelled",
            "overdue",
        ]:
            self.invoice_status = "overdue"

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
