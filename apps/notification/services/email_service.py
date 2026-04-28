from django.utils import timezone
import logging
from typing import Optional
from ..models import Notification
from apps.core.exceptions.base_exceptions import NotificationError


logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications"""

    @staticmethod
    def send_notification_email(notification: Notification) -> bool:
        """
        Send email notification
        """
        try:
            from django.core.mail import EmailMultiAlternatives
            from django.template.loader import render_to_string
            from django.utils.html import strip_tags
            from django.conf import settings

            # Prepare context
            context = {
                "user": notification.user,
                "notification": notification,
                "title": notification.title,
                "message": notification.message,
                "site_name": "MindCare Hub",
                "frontend_url": settings.FRONTEND_URL,
                "unsubscribe_url": f"{settings.FRONTEND_URL}/notifications/unsubscribe",
            }

            # Merge metadata
            if notification.metadata and "context" in notification.metadata:
                context.update(notification.metadata["context"])

            # Determine template
            template_name = EmailService._get_email_template(notification.category)

            # Render email
            html_content = render_to_string(f"{template_name}.html", context)
            text_content = strip_tags(html_content)

            # Create email
            email = EmailMultiAlternatives(
                subject=notification.title,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[notification.user.email],
                reply_to=(
                    [settings.SUPPORT_EMAIL]
                    if hasattr(settings, "SUPPORT_EMAIL")
                    else None
                ),
            )
            email.attach_alternative(html_content, "text/html")

            # Send email
            email.send(fail_silently=False)

            # Update notification
            notification.mark_as_sent("email")

            # Create log entry
            from ..models import NotificationLog

            NotificationLog.objects.create(
                notification=notification,
                channel="email",
                status="sent",
                provider="django_smtp",
                sent_at=timezone.now(),
            )

            logger.info(f"Email sent for notification {notification.id}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to send email for notification {notification.id}: {str(e)}"
            )

            # Create failure log
            from ..models import NotificationLog

            NotificationLog.objects.create(
                notification=notification,
                channel="email",
                status="failed",
                error_message=str(e)[:500],
                sent_at=timezone.now(),
            )

            # Update retry count
            notification.retry_count += 1
            notification.last_retry_at = timezone.now()
            notification.save(
                update_fields=["retry_count", "last_retry_at", "updated_at"]
            )

            # Retry if needed
            if notification.retry_count < notification.max_retries:
                from ..tasks import process_notification

                process_notification.apply_async(
                    args=[notification.id],
                    countdown=60 * (2**notification.retry_count),  # Exponential backoff
                )

            raise NotificationError(detail=f"Failed to send email: {str(e)}")

    @staticmethod
    def _get_email_template(category: str) -> str:
        """Get email template name for category"""
        template_map = {
            "auth": "auth_notification",
            "appointment": "appointment_notification",
            "medical": "medical_notification",
            "billing": "billing_notification",
            "system": "system_notification",
            "marketing": "marketing_notification",
        }
        return template_map.get(category, "base")
