from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class MedicalRecord(models.Model):
    """Patient medical records and consultation notes"""

    CONFIDENTIALITY_CHOICES = [
        ("standard", "Standard"),
        ("sensitive", "Sensitive"),
        ("highly_sensitive", "Highly Sensitive"),
    ]

    patient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="medical_records"
    )
    specialist = models.ForeignKey(
        "specialists.Specialist",
        on_delete=models.CASCADE,
        related_name="medical_records",
    )
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.CASCADE,
        related_name="medical_records",
    )
    diagnosis = models.TextField()
    prescription = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    follow_up_date = models.DateField(blank=True, null=True)
    confidentiality_level = models.CharField(
        max_length=20, choices=CONFIDENTIALITY_CHOICES, default="standard"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "medical_records"
        verbose_name = "Medical Record"
        verbose_name_plural = "Medical Records"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["patient", "created_at"]),
        ]

    def __str__(self):
        return f"Record for {self.patient.get_full_name()} - {self.created_at.date()}"
