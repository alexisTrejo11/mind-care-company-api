from django.db import models
from django.conf import settings


class SystemLog(models.Model):
    """Model to store application logs in database"""

    LEVEL_CHOICES = [
        ("DEBUG", "Debug"),
        ("INFO", "Info"),
        ("WARNING", "Warning"),
        ("ERROR", "Error"),
        ("CRITICAL", "Critical"),
    ]

    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, db_index=True)
    logger = models.CharField(max_length=255, db_index=True)
    message = models.TextField()
    module = models.CharField(max_length=255, blank=True, null=True)
    function = models.CharField(max_length=255, blank=True, null=True)
    line = models.IntegerField(blank=True, null=True)
    path = models.CharField(max_length=500, blank=True, null=True)
    exception = models.TextField(blank=True, null=True)

    # Request information
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="system_logs",
    )
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    request_method = models.CharField(max_length=10, blank=True, null=True)
    request_path = models.CharField(max_length=500, blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "System Log"
        verbose_name_plural = "System Logs"
        indexes = [
            models.Index(fields=["-created_at", "level"]),
            models.Index(fields=["logger", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.level}] {self.logger} - {self.message[:50]}"
