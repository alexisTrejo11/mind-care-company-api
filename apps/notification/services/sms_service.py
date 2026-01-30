from django.utils import timezone
import logging
from typing import Optional
from core.exceptions.base_exceptions import NotificationError
from ..models import Notification

logger = logging.getLogger(__name__)


class SMSService:
    """Service for sending SMS notifications via Twilio"""

    @staticmethod
    def send_notification_sms(notification: Notification) -> bool:
        """
        Send SMS notification using Twilio
        """
        try:
            from twilio.rest import Client
            from django.conf import settings

            if not hasattr(settings, "TWILIO_ACCOUNT_SID"):
                logger.warning("Twilio not configured, skipping SMS")
                return False

            # Get SMS message
            message = SMSService._get_sms_message(notification)

            if not message:
                logger.warning(f"No SMS message for notification {notification.id}")
                return False

            # Initialize Twilio client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

            # Send SMS
            twilio_response = client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=notification.user.phone,
            )

            # Update notification
            notification.mark_as_sent("sms")

            # Create log entry
            from ..models import NotificationLog

            NotificationLog.objects.create(
                notification=notification,
                channel="sms",
                status="sent",
                provider="twilio",
                provider_id=twilio_response.sid,
                provider_response={
                    "status": twilio_response.status,
                    "price": twilio_response.price,
                    "error_code": twilio_response.error_code,
                    "error_message": twilio_response.error_message,
                },
                sent_at=timezone.now(),
            )

            logger.info(f"SMS sent for notification {notification.id}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to send SMS for notification {notification.id}: {str(e)}"
            )

            # Create failure log
            from ..models import NotificationLog

            NotificationLog.objects.create(
                notification=notification,
                channel="sms",
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

            raise NotificationError(detail=f"Failed to send SMS: {str(e)}")

    @staticmethod
    def _get_sms_message(notification: Notification) -> str:
        """Get SMS message from notification"""
        # Try to get from metadata
        if notification.metadata and "rendered_content" in notification.metadata:
            rendered = notification.metadata["rendered_content"]
            if "sms_message" in rendered:
                return rendered["sms_message"]

        # Fallback: truncate regular message
        return notification.message[:160]  # SMS character limit
