from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator

User = get_user_model()


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
        "billing.Payment", on_delete=models.CASCADE, related_name="refunds"
    )
    bill = models.ForeignKey(
        "billing.Bill", on_delete=models.CASCADE, related_name="refunds"
    )

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
