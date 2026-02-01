from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
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
        Payment.objects.create(
            bill=self,
            amount=amount,
            payment_method=payment_method or self.payment_method,
            notes=notes,
            status="completed",
        )

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


class Payment(models.Model):
    """Payment transactions"""

    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_METHOD_CHOICES = Bill.PAYMENT_METHOD_CHOICES

    # Reference
    payment_number = models.CharField(max_length=20, unique=True, editable=False)
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="payments")
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments")

    # Payment details
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    currency = models.CharField(max_length=3, default="USD")

    # Status
    status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending"
    )

    # Stripe integration
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_charge_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_refund_id = models.CharField(max_length=100, blank=True, null=True)

    # Card details (PCI compliant storage - consider tokenization)
    card_last4 = models.CharField(max_length=4, blank=True, null=True)
    card_brand = models.CharField(max_length=20, blank=True, null=True)
    card_exp_month = models.IntegerField(null=True, blank=True)
    card_exp_year = models.IntegerField(null=True, blank=True)

    # Insurance payment
    is_insurance_payment = models.BooleanField(default=False)
    insurance_claim_id = models.CharField(max_length=100, blank=True, null=True)

    # Notes
    notes = models.TextField(blank=True)
    error_message = models.TextField(blank=True)

    # Dates
    payment_date = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_payments"
    )

    class Meta:
        db_table = "payments"
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-payment_date"]
        indexes = [
            models.Index(fields=["payment_number"]),
            models.Index(fields=["bill", "status"]),
            models.Index(fields=["patient", "payment_date"]),
            models.Index(fields=["stripe_payment_intent_id"]),
        ]

    def __str__(self):
        return f"Payment #{self.payment_number} - ${self.amount} - {self.status}"

    def save(self, *args, **kwargs):
        """Generate payment number on creation"""
        if not self.payment_number:
            self.payment_number = self.generate_payment_number()
        super().save(*args, **kwargs)

    def generate_payment_number(self):
        """Generate unique payment number: PAY-YYYYMM-XXXX"""
        from django.utils import timezone

        year_month = timezone.now().strftime("%Y%m")
        last_payment = (
            Payment.objects.filter(payment_number__startswith=f"PAY-{year_month}-")
            .order_by("payment_number")
            .last()
        )

        if last_payment:
            last_number = int(last_payment.payment_number.split("-")[-1])
            new_number = last_number + 1
        else:
            new_number = 1

        return f"PAY-{year_month}-{new_number:04d}"

    def mark_as_completed(self):
        """Mark payment as completed"""
        from django.utils import timezone

        self.status = "completed"
        self.processed_at = timezone.now()
        self.save()

        # Update bill
        self.bill.mark_as_paid(
            amount=self.amount,
            payment_method=self.payment_method,
            notes=f"Payment #{self.payment_number}",
        )

    def mark_as_failed(self, error_message=""):
        """Mark payment as failed"""
        self.status = "failed"
        self.error_message = error_message
        self.save()

    def refund(self, amount=None, notes=""):
        """Refund payment"""
        from django.utils import timezone

        if amount is None:
            amount = self.amount

        if amount > self.amount:
            raise ValueError("Refund amount cannot exceed original payment")

        # Create refund record
        Refund.objects.create(
            payment=self, amount=amount, reason=notes, status="completed"
        )

        # Update payment
        self.status = "refunded"
        self.refunded_at = timezone.now()
        self.save()

        # Update bill
        self.bill.amount_paid -= amount
        self.bill.update_payment_status()
        self.bill.save()


class Refund(models.Model):
    """Refund transactions"""

    REFUND_STATUS_CHOICES = [
        ("requested", "Requested"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    REFUND_REASON_CHOICES = [
        ("duplicate", "Duplicate Payment"),
        ("fraudulent", "Fraudulent Payment"),
        ("requested_by_customer", "Requested by Customer"),
        ("service_not_provided", "Service Not Provided"),
        ("cancelled_appointment", "Cancelled Appointment"),
        ("other", "Other"),
    ]

    # Reference
    refund_number = models.CharField(max_length=20, unique=True, editable=False)
    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name="refunds"
    )
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="refunds")

    # Refund details
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    reason = models.CharField(
        max_length=50, choices=REFUND_REASON_CHOICES, default="other"
    )
    reason_details = models.TextField(blank=True)

    # Status
    status = models.CharField(
        max_length=20, choices=REFUND_STATUS_CHOICES, default="requested"
    )

    # Stripe integration
    stripe_refund_id = models.CharField(max_length=100, blank=True, null=True)

    # Dates
    requested_date = models.DateTimeField(auto_now_add=True)
    processed_date = models.DateTimeField(null=True, blank=True)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_refunds"
    )

    class Meta:
        db_table = "refunds"
        verbose_name = "Refund"
        verbose_name_plural = "Refunds"
        ordering = ["-requested_date"]

    def __str__(self):
        return f"Refund #{self.refund_number} - ${self.amount}"

    def save(self, *args, **kwargs):
        """Generate refund number on creation"""
        if not self.refund_number:
            self.refund_number = self.generate_refund_number()
        super().save(*args, **kwargs)

    def generate_refund_number(self):
        """Generate unique refund number: REF-YYYYMM-XXXX"""
        from django.utils import timezone

        year_month = timezone.now().strftime("%Y%m")
        last_refund = (
            Refund.objects.filter(refund_number__startswith=f"REF-{year_month}-")
            .order_by("refund_number")
            .last()
        )

        if last_refund:
            last_number = int(last_refund.refund_number.split("-")[-1])
            new_number = last_number + 1
        else:
            new_number = 1

        return f"REF-{year_month}-{new_number:04d}"

    def mark_as_completed(self):
        """Mark refund as completed"""
        from django.utils import timezone

        self.status = "completed"
        self.processed_date = timezone.now()
        self.save()


class InsuranceClaim(models.Model):
    """Insurance claims processing"""

    CLAIM_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("acknowledged", "Acknowledged"),
        ("under_review", "Under Review"),
        ("approved", "Approved"),
        ("partially_approved", "Partially Approved"),
        ("denied", "Denied"),
        ("paid", "Paid"),
        ("appealed", "Appealed"),
        ("closed", "Closed"),
    ]

    # Reference
    claim_number = models.CharField(max_length=50, unique=True)
    bill = models.OneToOneField(
        Bill, on_delete=models.CASCADE, related_name="insurance_claim"
    )
    patient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="insurance_claims"
    )

    # Insurance details
    insurance_company = models.CharField(max_length=100)
    policy_number = models.CharField(max_length=50)
    group_number = models.CharField(max_length=50, blank=True, null=True)
    subscriber_name = models.CharField(max_length=100)
    subscriber_relationship = models.CharField(
        max_length=20
    )  # self, spouse, child, etc.

    # Claim details
    diagnosis_codes = models.JSONField(default=list)  # ICD-10 codes
    procedure_codes = models.JSONField(default=list)  # CPT/HCPCS codes
    total_claimed_amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    insurance_responsibility = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    patient_responsibility = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    denied_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    # Status
    status = models.CharField(
        max_length=20, choices=CLAIM_STATUS_CHOICES, default="draft"
    )

    # Dates
    date_of_service = models.DateField()
    date_submitted = models.DateField(null=True, blank=True)
    date_acknowledged = models.DateField(null=True, blank=True)
    date_processed = models.DateField(null=True, blank=True)
    date_paid = models.DateField(null=True, blank=True)

    # EDI/File tracking
    edi_file_name = models.CharField(max_length=200, blank=True, null=True)
    edi_reference_number = models.CharField(max_length=100, blank=True, null=True)
    payer_claim_number = models.CharField(max_length=100, blank=True, null=True)

    # Notes
    notes = models.TextField(blank=True)
    denial_reason = models.TextField(blank=True)
    appeal_notes = models.TextField(blank=True)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_insurance_claims",
    )

    class Meta:
        db_table = "insurance_claims"
        verbose_name = "Insurance Claim"
        verbose_name_plural = "Insurance Claims"
        ordering = ["-date_submitted"]

    def __str__(self):
        return f"Claim #{self.claim_number} - {self.patient.get_full_name()}"


class PaymentMethod(models.Model):
    """Stored payment methods for patients"""

    PAYMENT_METHOD_TYPE_CHOICES = [
        ("card", "Credit/Debit Card"),
        ("bank_account", "Bank Account"),
        ("wallet", "Digital Wallet"),
    ]

    patient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="payment_methods"
    )
    method_type = models.CharField(max_length=20, choices=PAYMENT_METHOD_TYPE_CHOICES)
    is_default = models.BooleanField(default=False)

    # Stripe integration
    stripe_payment_method_id = models.CharField(max_length=100, unique=True)
    stripe_customer_id = models.CharField(max_length=100)

    # Card details (for display only)
    card_brand = models.CharField(max_length=20, blank=True, null=True)
    card_last4 = models.CharField(max_length=4, blank=True, null=True)
    card_exp_month = models.IntegerField(null=True, blank=True)
    card_exp_year = models.IntegerField(null=True, blank=True)

    # Bank account details
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_last4 = models.CharField(max_length=4, blank=True, null=True)
    account_type = models.CharField(
        max_length=20, blank=True, null=True
    )  # checking, savings

    # Status
    is_active = models.BooleanField(default=True)

    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_methods"
        verbose_name = "Payment Method"
        verbose_name_plural = "Payment Methods"
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        if self.card_brand:
            return f"{self.card_brand} ****{self.card_last4}"
        elif self.bank_name:
            return f"{self.bank_name} ****{self.account_last4}"
        return f"Payment Method {self.id}"
