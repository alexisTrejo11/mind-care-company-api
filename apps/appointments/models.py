from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model

User = get_user_model()


class Appointment(models.Model):
    APPOINTMENT_TYPE_CHOICES = [
        ("consultation", "Consultation"),
        ("therapy", "Therapy"),
        ("follow_up", "Follow-up"),
        ("emergency", "Emergency"),
    ]

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("confirmed", "Confirmed"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("no_show", "No Show"),
    ]

    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="appointments",
    )

    specialist = models.ForeignKey(
        "specialists.Specialist",
        on_delete=models.CASCADE,
        related_name="appointments",
    )

    appointment_type = models.CharField(
        max_length=20,
        choices=APPOINTMENT_TYPE_CHOICES,
    )

    appointment_date = models.DateTimeField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration_minutes = models.IntegerField(validators=[MinValueValidator(5)])
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="scheduled"
    )
    notes = models.TextField(blank=True, default="")
    symptoms = models.TextField(blank=True, default="")

    # For virtual appointments
    meeting_link = models.URLField(max_length=500, blank=True, null=True)

    # For physical appointments
    room_number = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "appointments"
        verbose_name = "Appointment"
        verbose_name_plural = "Appointments"
        ordering = ["-appointment_date", "start_time"]
        indexes = [
            models.Index(fields=["appointment_date", "specialist"]),
            models.Index(fields=["patient", "status"]),
        ]

    def is_from_specialist(self, specialist):
        return self.specialist == specialist

    def __str__(self):
        return f"{self.patient.get_full_name()} with {self.specialist.user.get_full_name()} on {self.appointment_date}"
