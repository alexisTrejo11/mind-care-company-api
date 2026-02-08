from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.forms import ValidationError
from django.utils import timezone
from decimal import Decimal

User = get_user_model()


class Payment(models.Model):
    """Payment transaction - Each individual payment"""

    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
        ("cancelled", "Cancelled"),
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

    # Reference
    id = models.AutoField(primary_key=True)
    payment_number = models.CharField(max_length=20, unique=True, editable=False)
    # Usamos ForeignKey con string para evitar importación circular
    bill = models.ForeignKey(
        "billing.Bill", on_delete=models.CASCADE, related_name="payments"
    )
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments")

    # Payment details
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)

    # Bank transfer details
    bank_reference = models.CharField(max_length=100, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)

    # Stripe integration
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_charge_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_refund_id = models.CharField(max_length=100, blank=True, null=True)

    # Card details
    card_last4 = models.CharField(max_length=4, blank=True, null=True)
    card_brand = models.CharField(max_length=20, blank=True, null=True)
    card_exp_month = models.IntegerField(null=True, blank=True)
    card_exp_year = models.IntegerField(null=True, blank=True)

    # Status
    status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending"
    )

    # Notes
    notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)

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
            models.Index(fields=["payment_method"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Payment #{self.payment_number} - ${self.amount} - {self.status}"

    def save(self, *args, **kwargs):
        """Generate payment number on creation"""
        if not self.payment_number:
            self.payment_number = self.generate_payment_number()

        # Auto-generate reference for cash payments
        if self.payment_method == "cash" and not self.bank_reference:
            self.bank_reference = f"CASH-{self.payment_number}"

        super().save(*args, **kwargs)

        # Update related bill status
        if self.status == "completed":
            self.bill.update_status_if_needed()
            self.bill.save()

    def generate_payment_number(self):
        """Generate unique payment number: PAY-YYYYMM-XXXX"""
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

    def clean(self):
        """Validate payment data"""
        from django.core.exceptions import ValidationError

        if self.payment_method == "bank_transfer" and not self.bank_reference:
            raise ValidationError(
                {"bank_reference": "Bank reference is required for bank transfers"}
            )

        if self.payment_method == "bank_transfer" and not self.bank_name:
            raise ValidationError(
                {"bank_name": "Bank name is required for bank transfers"}
            )

    def mark_as_completed(self):
        """Mark payment as completed"""
        self.status = "completed"
        self.processed_at = timezone.now()
        self.save()

    def mark_as_failed(self, error_message=""):
        """Mark payment as failed"""
        self.status = "failed"
        if error_message:
            self.admin_notes = f"Failed: {error_message}"
        self.save()

    def refund(self, amount=None, notes=""):
        """Refund payment"""
        if amount is None:
            amount = self.amount

        if amount > self.amount:
            raise ValueError("Refund amount cannot exceed original payment")

        # Update payment status
        self.status = "refunded"
        self.refunded_at = timezone.now()
        if notes:
            self.admin_notes = f"{self.admin_notes}\nRefund: {notes}"
        self.save()


class PaymentMethod(models.Model):
    """Stored payment methods for patients"""

    PAYMENT_METHOD_TYPE_CHOICES = [
        ("card", "Credit/Debit Card"),  # Cambiado de "digital payment" a "card"
        ("cash", "Cash"),
        ("bank_transfer", "Bank Transfer"),
        ("digital_wallet", "Digital Wallet"),  # PayPal, Apple Pay, etc.
    ]

    # Basic information
    id = models.AutoField(primary_key=True)
    patient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="payment_methods"
    )
    method_type = models.CharField(max_length=20, choices=PAYMENT_METHOD_TYPE_CHOICES)
    is_default = models.BooleanField(default=False)

    # Display name (opcional, para que el usuario le ponga nombre: "Mi tarjeta principal")
    nickname = models.CharField(max_length=50, blank=True, null=True)

    # Stripe integration (para pagos online con tarjeta)
    stripe_payment_method_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)

    # Card details (solo para tipo "card")
    card_brand = models.CharField(max_length=20, blank=True, null=True)
    card_last4 = models.CharField(max_length=4, blank=True, null=True)
    card_exp_month = models.IntegerField(null=True, blank=True)
    card_exp_year = models.IntegerField(null=True, blank=True)

    # Bank account details (solo para tipo "bank_transfer")
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_last4 = models.CharField(max_length=4, blank=True, null=True)
    account_type = models.CharField(
        max_length=20, blank=True, null=True
    )  # checking, savings
    routing_number = models.CharField(max_length=20, blank=True, null=True)

    # Digital wallet details (solo para tipo "digital_wallet")
    wallet_type = models.CharField(
        max_length=20, blank=True, null=True
    )  # paypal, apple_pay, google_pay
    wallet_email = models.EmailField(blank=True, null=True)

    # Status
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(
        default=False
    )  # Para cuentas bancarias que necesitan verificación

    # Security
    last_used = models.DateTimeField(null=True, blank=True)

    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_methods"
        verbose_name = "Payment Method"
        verbose_name_plural = "Payment Methods"
        ordering = ["-is_default", "-created_at"]
        unique_together = [["patient", "stripe_payment_method_id"]]

    def __str__(self):
        if self.nickname:
            return self.nickname

        if self.method_type == "card" and self.card_brand and self.card_last4:
            return f"{self.card_brand} ****{self.card_last4}"
        elif (
            self.method_type == "bank_transfer"
            and self.bank_name
            and self.account_last4
        ):
            return f"{self.bank_name} ****{self.account_last4}"
        elif self.method_type == "digital_wallet" and self.wallet_type:
            return f"{self.wallet_type.title()} ({self.wallet_email or ''})"
        elif self.method_type == "cash":
            return "Cash"

        return f"Payment Method {self.id}"

    def clean(self):
        """Validate that the method type matches the provided details"""
        errors = {}

        if self.method_type == "card":
            # Require card details for card payments
            if not self.stripe_payment_method_id:
                errors["stripe_payment_method_id"] = (
                    "Stripe payment method ID is required for cards"
                )
            if not self.card_brand:
                errors["card_brand"] = "Card brand is required"
            if not self.card_last4 or len(self.card_last4) != 4:
                errors["card_last4"] = "Valid card last 4 digits are required"
            if not self.card_exp_month:
                errors["card_exp_month"] = "Card expiration month is required"
            if not self.card_exp_year:
                errors["card_exp_year"] = "Card expiration year is required"

            # Don't allow bank fields for cards
            if self.bank_name or self.account_last4:
                errors["bank_fields"] = (
                    "Bank details should not be provided for card payments"
                )

        elif self.method_type == "bank_transfer":
            # Require bank details for transfers
            if not self.bank_name:
                errors["bank_name"] = "Bank name is required for bank transfers"
            if not self.account_last4 or len(self.account_last4) != 4:
                errors["account_last4"] = "Valid account last 4 digits are required"

            # Don't allow card fields for bank transfers
            if self.card_brand or self.card_last4:
                errors["card_fields"] = (
                    "Card details should not be provided for bank transfers"
                )

        elif self.method_type == "cash":
            # Don't allow any payment method specific fields for cash
            if (
                self.stripe_payment_method_id
                or self.card_brand
                or self.card_last4
                or self.bank_name
                or self.account_last4
                or self.wallet_type
            ):
                errors["method_fields"] = (
                    "No payment details should be provided for cash method"
                )

        elif self.method_type == "digital_wallet":
            # Require wallet type
            if not self.wallet_type:
                errors["wallet_type"] = "Wallet type is required for digital wallets"

            # Don't allow card or bank fields for wallets
            if (
                self.card_brand
                or self.card_last4
                or self.bank_name
                or self.account_last4
            ):
                errors["other_fields"] = (
                    "Card or bank details should not be provided for digital wallets"
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Handle default payment method logic"""
        # If this is being set as default, unset default from other methods
        if self.is_default and self.is_active:
            PaymentMethod.objects.filter(
                patient=self.patient, is_default=True, is_active=True
            ).exclude(id=self.id).update(is_default=False)

        super().save(*args, **kwargs)

    def mark_as_used(self):
        """Update last used timestamp"""
        self.last_used = timezone.now()
        self.save(update_fields=["last_used"])

    @property
    def requires_stripe(self):
        """Determine if this payment method requires Stripe integration"""
        return self.method_type in ["card", "digital_wallet"]

    @property
    def display_name(self):
        """Get display name for the payment method"""
        return str(self)

    @property
    def is_expired(self):
        """Check if card is expired (only for card type)"""
        if (
            self.method_type != "card"
            or not self.card_exp_month
            or not self.card_exp_year
        ):
            return False

        current_year = timezone.now().year
        current_month = timezone.now().month

        # Convert 2-digit year to 4-digit (e.g., 24 -> 2024, 99 -> 1999)
        exp_year = (
            self.card_exp_year
            if self.card_exp_year >= 100
            else self.card_exp_year + 2000
        )

        return (exp_year < current_year) or (
            exp_year == current_year and self.card_exp_month < current_month
        )

    def get_payment_details(self):
        """Get safe payment details for display"""
        if self.method_type == "card":
            return {
                "type": "card",
                "brand": self.card_brand,
                "last4": self.card_last4,
                "exp_month": self.card_exp_month,
                "exp_year": self.card_exp_year,
                "expired": self.is_expired,
            }
        elif self.method_type == "bank_transfer":
            return {
                "type": "bank_transfer",
                "bank_name": self.bank_name,
                "account_last4": self.account_last4,
                "account_type": self.account_type,
            }
        elif self.method_type == "digital_wallet":
            return {
                "type": "digital_wallet",
                "wallet_type": self.wallet_type,
                "email": self.wallet_email,
            }
        elif self.method_type == "cash":
            return {"type": "cash"}

        return {"type": self.method_type}


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
        "billing.Bill", on_delete=models.CASCADE, related_name="insurance_claim"
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
