from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
import decimal

User = get_user_model()


class Specialist(models.Model):
    """Healthcare specialists profile information"""

    SPECIALIZATION_CHOICES = [
        ("psychologist", "Psychologist"),
        ("psychiatrist", "Psychiatrist"),
        ("therapist", "Therapist"),
        ("counselor", "Counselor"),
        ("general_physician", "General Physician"),
        ("nutritionist", "Nutritionist"),
        ("physiotherapist", "Physiotherapist"),
        ("neurologist", "Neurologist"),
        ("other", "Other"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="specialist_profile"
    )
    license_number = models.CharField(max_length=50, unique=True)
    specialization = models.CharField(max_length=50, choices=SPECIALIZATION_CHOICES)
    qualifications = models.TextField(blank=True)
    years_experience = models.IntegerField(validators=[MinValueValidator(0)])
    consultation_fee = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    is_accepting_new_patients = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    max_daily_appointments = models.IntegerField(
        default=20, validators=[MinValueValidator(1)]
    )
    bio = models.TextField(blank=True)
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=decimal.Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )

    def can_handle_appointment_type(self, appointment_type):
        """Check if specialist can handle this appointment type"""
        # For now, all specialists can handle all appointment types
        # This can be extended with more complex logic
        return True


class Service(models.Model):
    """Healthcare services offered by the facility"""

    CATEGORY_CHOICES = [
        ("mental_health", "Mental Health"),
        ("general_medicine", "General Medicine"),
        ("specialist_consultation", "Specialist Consultation"),
        ("diagnostic", "Diagnostic"),
        ("therapy", "Therapy"),
        ("wellness", "Wellness"),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    duration_minutes = models.IntegerField(validators=[MinValueValidator(5)])
    base_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "services"
        verbose_name = "Service"
        verbose_name_plural = "Services"
        ordering = ["category", "name"]
        indexes = [
            models.Index(fields=["category", "name"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"  # type: ignore[attr-defined]


class SpecialistService(models.Model):
    """Junction table linking specialists to services they offer"""

    specialist = models.ForeignKey(
        Specialist, on_delete=models.CASCADE, related_name="services"
    )
    service = models.ForeignKey(
        Service, on_delete=models.CASCADE, related_name="specialists"
    )
    price_override = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
    )
    is_available = models.BooleanField(default=True)

    class Meta:
        db_table = "specialist_services"
        verbose_name = "Specialist Service"
        verbose_name_plural = "Specialist Services"
        unique_together = ["specialist", "service"]

    def __str__(self):
        return f"{self.specialist.user.get_full_name()} - {self.service.name}"

    def get_price(self):
        """Return the effective price (override or base price)"""
        return self.price_override if self.price_override else self.service.base_price


class Availability(models.Model):
    """Specialist availability schedule"""

    DAY_CHOICES = [
        (0, "Sunday"),
        (1, "Monday"),
        (2, "Tuesday"),
        (3, "Wednesday"),
        (4, "Thursday"),
        (5, "Friday"),
        (6, "Saturday"),
    ]

    specialist = models.ForeignKey(
        "specialists.Specialist", on_delete=models.CASCADE, related_name="availability"
    )
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_recurring = models.BooleanField(default=True)
    valid_from = models.DateField()
    valid_until = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "availability"
        verbose_name = "Availability"
        verbose_name_plural = "Availabilities"
        ordering = ["specialist", "day_of_week", "start_time"]
        indexes = [
            models.Index(fields=["specialist", "day_of_week", "start_time"]),
        ]

    def __str__(self):
        return f"{self.specialist.user.get_full_name()} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"  # type: ignore[attr-defined]
