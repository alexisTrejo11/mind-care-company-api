from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class Notification(models.Model):
    """User notifications and reminders"""

    TYPE_CHOICES = [
        ("email", "Email Notification"),
        ("sms", "SMS Notification"),
        ("push", "Push Notification"),
        ("in_app", "In-App Notification"),
    ]

    CATEGORY_CHOICES = [
        ("auth", "Authentication"),
        ("appointment", "Appointment"),
        ("medical", "Medical Records"),
        ("billing", "Billing"),
        ("system", "System"),
        ("marketing", "Marketing"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("queued", "Queued"),
        ("sending", "Sending"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="medium"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)  # Additional data

    # Channels
    send_email = models.BooleanField(default=True)
    send_sms = models.BooleanField(default=False)
    send_push = models.BooleanField(default=False)

    # Tracking
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)

    # Delivery tracking
    email_delivered_at = models.DateTimeField(null=True, blank=True)
    sms_delivered_at = models.DateTimeField(null=True, blank=True)
    push_delivered_at = models.DateTimeField(null=True, blank=True)

    # Failure tracking
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)

    # User interaction
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # Scheduling
    scheduled_for = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notifications"
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["status", "scheduled_for"]),
            models.Index(fields=["category", "priority"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.get_full_name()}"

    def mark_as_read(self):
        """Mark notification as read"""
        from django.utils import timezone

        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at", "updated_at"])

    def mark_as_sent(self, channel):
        """Mark notification as sent for specific channel"""
        from django.utils import timezone

        if channel == "email":
            self.email_sent = True
            self.email_delivered_at = timezone.now()
        elif channel == "sms":
            self.sms_sent = True
            self.sms_delivered_at = timezone.now()
        elif channel == "push":
            self.push_sent = True
            self.push_delivered_at = timezone.now()

        # Update overall status if all channels are sent
        if (
            self.email_sent
            and (not self.send_sms or self.sms_sent)
            and (not self.send_push or self.push_sent)
        ):
            self.status = "sent"

        self.save()


class NotificationTemplate(models.Model):
    """Reusable notification templates"""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    notification_type = models.CharField(
        max_length=20, choices=Notification.TYPE_CHOICES
    )
    category = models.CharField(max_length=20, choices=Notification.CATEGORY_CHOICES)

    # Templates
    email_subject = models.CharField(max_length=200)
    email_template = models.TextField(
        help_text="HTML template with variables in {{ }} format"
    )

    sms_template = models.TextField(
        max_length=500,
        blank=True,
        help_text="SMS template (max 500 chars) with variables in {{ }} format",
    )

    push_title = models.CharField(max_length=100, blank=True)
    push_template = models.TextField(
        max_length=200,
        blank=True,
        help_text="Push notification template (max 200 chars)",
    )

    # Default settings
    default_priority = models.CharField(
        max_length=10, choices=Notification.PRIORITY_CHOICES, default="medium"
    )

    send_email = models.BooleanField(default=True)
    send_sms = models.BooleanField(default=False)
    send_push = models.BooleanField(default=False)

    # Variables documentation
    variables = models.JSONField(
        default=dict, help_text="JSON describing available template variables"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_templates"
        verbose_name = "Notification Template"
        verbose_name_plural = "Notification Templates"

    def __str__(self):
        return self.name


class NotificationPreference(models.Model):
    """User notification preferences"""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="notification_preferences"
    )

    # Email preferences
    email_auth = models.BooleanField(default=True)
    email_appointments = models.BooleanField(default=True)
    email_medical = models.BooleanField(default=True)
    email_billing = models.BooleanField(default=True)
    email_system = models.BooleanField(default=True)
    email_marketing = models.BooleanField(default=False)

    # SMS preferences
    sms_auth = models.BooleanField(default=False)
    sms_appointments = models.BooleanField(default=True)
    sms_medical = models.BooleanField(default=False)
    sms_billing = models.BooleanField(default=False)
    sms_system = models.BooleanField(default=False)
    sms_marketing = models.BooleanField(default=False)

    # Push preferences
    push_auth = models.BooleanField(default=True)
    push_appointments = models.BooleanField(default=True)
    push_medical = models.BooleanField(default=True)
    push_billing = models.BooleanField(default=True)
    push_system = models.BooleanField(default=True)
    push_marketing = models.BooleanField(default=False)

    # Global settings
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    timezone = models.CharField(max_length=50, default="UTC")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_preferences"
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"

    def __str__(self):
        return f"Preferences for {self.user.get_full_name()}"

    def can_receive_notification(self, category, channel):
        """Check if user can receive notification of given category via channel"""
        channel_prefix = channel.lower()
        field_name = f"{channel_prefix}_{category}"

        if hasattr(self, field_name):
            return getattr(self, field_name)

        return False  # Default to not receiving if preference not found


class NotificationLog(models.Model):
    """Audit log for notification delivery"""

    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="logs"
    )
    channel = models.CharField(max_length=20, choices=Notification.TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=Notification.STATUS_CHOICES)

    # Delivery details
    provider = models.CharField(max_length=50, blank=True)
    provider_id = models.CharField(max_length=100, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)

    # Timing
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Error tracking
    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)

    # Retry info
    retry_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notification_logs"
        verbose_name = "Notification Log"
        verbose_name_plural = "Notification Logs"
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["notification", "channel"]),
            models.Index(fields=["status", "sent_at"]),
        ]

    def __str__(self):
        return f"{self.notification.title} - {self.channel} - {self.status}"
