from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator

User = get_user_model()


class Bill(models.Model):
    """Billing and payment information"""

    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("partial", "Partial"),
        ("paid", "Paid"),
        ("insurance_pending", "Insurance Pending"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("insurance", "Insurance"),
        ("online", "Online"),
    ]

    appointment = models.OneToOneField(
        "appointments.Appointment", on_delete=models.CASCADE, related_name="bill"
    )
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bills")
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending"
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True
    )
    insurance_company = models.CharField(max_length=100, blank=True, null=True)
    policy_number = models.CharField(max_length=50, blank=True, null=True)
    invoice_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()

    class Meta:
        db_table = "bills"
        verbose_name = "Bill"
        verbose_name_plural = "Bills"
        ordering = ["-invoice_date"]
        indexes = [
            models.Index(fields=["payment_status"]),
            models.Index(fields=["due_date"]),
        ]

    def __str__(self):
        return f"Bill #{self.id if self.id else 'N/A'} - {self.patient.get_full_name()} - ${self.amount}"
