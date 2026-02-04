"""
SMS Service with Twilio Integration
"""

from django.utils import timezone
from django.conf import settings
import logging
from typing import Optional
from apps.core.exceptions.base_exceptions import NotificationError
from ..models import Notification

logger = logging.getLogger(__name__)


class SMSService:
    """Service for sending SMS notifications via Twilio"""

    @staticmethod
    def send_notification_sms(notification: Notification) -> bool:
        """
        Send SMS notification using Twilio

        Args:
            notification: Notification object to send

        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            # Check if Twilio is configured
            if not SMSService._is_twilio_configured():
                logger.warning("Twilio not configured, skipping SMS")
                return False

            # Get SMS message
            message = SMSService._get_sms_message(notification)

            if not message:
                logger.warning(f"No SMS message for notification {notification.id}")
                return False

            # Validate phone number
            if not notification.user.phone:
                logger.warning(f"User {notification.user.user_id} has no phone number")
                return False

            # Format phone number
            phone_number = SMSService._format_phone_number(notification.user.phone)

            # Initialize Twilio client
            from twilio.rest import Client

            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

            # Send SMS
            twilio_response = client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone_number,
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
                    "price_unit": twilio_response.price_unit,
                    "error_code": twilio_response.error_code,
                    "error_message": twilio_response.error_message,
                    "num_segments": twilio_response.num_segments,
                },
                sent_at=timezone.now(),
            )

            logger.info(
                f"SMS sent for notification {notification.id} - "
                f"SID: {twilio_response.sid}, Status: {twilio_response.status}"
            )

            return True

        except Exception as e:
            logger.error(
                f"Failed to send SMS for notification {notification.id}: {str(e)}",
                exc_info=True,
            )

            # Create failure log
            from ..models import NotificationLog

            NotificationLog.objects.create(
                notification=notification,
                channel="sms",
                status="failed",
                provider="twilio",
                error_message=str(e)[:500],
                sent_at=timezone.now(),
            )

            # Update retry count
            notification.retry_count += 1
            notification.last_retry_at = timezone.now()
            notification.failure_reason = f"SMS Error: {str(e)[:200]}"
            notification.save(
                update_fields=[
                    "retry_count",
                    "last_retry_at",
                    "failure_reason",
                    "updated_at",
                ]
            )

            # Retry if needed
            if notification.retry_count < notification.max_retries:
                from ..tasks import process_notification

                countdown = 60 * (2**notification.retry_count)  # Exponential backoff
                process_notification.apply_async(
                    args=[notification.id],
                    countdown=countdown,
                )
                logger.info(
                    f"Scheduled retry for notification {notification.id} in {countdown}s"
                )

            return False

    @staticmethod
    def send_verification_code(phone_number: str, code: str) -> bool:
        """
        Send verification code via SMS

        Args:
            phone_number: Phone number to send to
            code: Verification code

        Returns:
            bool: True if sent successfully
        """
        try:
            if not SMSService._is_twilio_configured():
                logger.warning("Twilio not configured")
                return False

            from twilio.rest import Client

            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

            formatted_phone = SMSService._format_phone_number(phone_number)

            message = f"Tu código de verificación de MindCare Hub es: {code}\n\nEste código expira en 10 minutos."

            response = client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=formatted_phone,
            )

            logger.info(
                f"Verification code sent to {formatted_phone} - SID: {response.sid}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send verification code: {str(e)}")
            return False

    @staticmethod
    def send_bulk_sms(phone_numbers: list, message: str) -> dict:
        """
        Send SMS to multiple recipients

        Args:
            phone_numbers: List of phone numbers
            message: Message to send

        Returns:
            dict: Results with success/failure counts
        """
        if not SMSService._is_twilio_configured():
            return {"error": "Twilio not configured"}

        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        results = {"total": len(phone_numbers), "success": 0, "failed": 0, "errors": []}

        for phone in phone_numbers:
            try:
                formatted_phone = SMSService._format_phone_number(phone)

                response = client.messages.create(
                    body=message,
                    from_=settings.TWILIO_PHONE_NUMBER,
                    to=formatted_phone,
                )

                results["success"] += 1
                logger.info(f"Bulk SMS sent to {formatted_phone} - SID: {response.sid}")

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"phone": phone, "error": str(e)})
                logger.error(f"Failed to send bulk SMS to {phone}: {str(e)}")

        return results

    # ========== PRIVATE HELPER METHODS ==========

    @staticmethod
    def _is_twilio_configured() -> bool:
        """Check if Twilio is properly configured"""
        return all(
            [
                hasattr(settings, "TWILIO_ACCOUNT_SID"),
                hasattr(settings, "TWILIO_AUTH_TOKEN"),
                hasattr(settings, "TWILIO_PHONE_NUMBER"),
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN,
                settings.TWILIO_PHONE_NUMBER,
            ]
        )

    @staticmethod
    def _get_sms_message(notification: Notification) -> str:
        """
        Get SMS message from notification

        Returns:
            str: Formatted SMS message (max 1600 characters for concatenated SMS)
        """
        # Try to get from metadata (rendered template)
        if notification.metadata and "rendered_content" in notification.metadata:
            rendered = notification.metadata["rendered_content"]
            if "sms_message" in rendered:
                return rendered["sms_message"]

        # Build default message
        # SMS best practices: Clear, concise, actionable
        message_parts = []

        # Add title/subject
        if notification.title:
            message_parts.append(f"MindCare Hub: {notification.title}")

        # Add main message (truncated if too long)
        if notification.message:
            # Remove HTML tags if present
            import re

            clean_message = re.sub(r"<[^>]+>", "", notification.message)
            # Limit to reasonable SMS length
            if len(clean_message) > 300:
                clean_message = clean_message[:297] + "..."
            message_parts.append(clean_message)

        # Add action URL if available
        if notification.metadata and "url" in notification.metadata:
            message_parts.append(f"\nVer más: {notification.metadata['url']}")

        full_message = "\n\n".join(message_parts)

        # Twilio supports up to 1600 characters (concatenated SMS)
        # But we limit to 500 for better delivery
        if len(full_message) > 500:
            full_message = full_message[:497] + "..."

        return full_message

    @staticmethod
    def _format_phone_number(phone: str) -> str:
        """
        Format phone number for Twilio

        Twilio requires E.164 format: +[country code][number]
        Examples:
            +14155552671 (US)
            +525512345678 (Mexico)

        Args:
            phone: Phone number to format

        Returns:
            str: Formatted phone number
        """
        # Remove all non-digit characters
        digits = "".join(filter(str.isdigit, phone))

        # If already has +, keep it
        if phone.startswith("+"):
            return phone

        # If 10 digits and no country code, assume Mexico (+52)
        if len(digits) == 10:
            return f"+52{digits}"

        # If 11 digits and starts with 1, assume US (+1)
        if len(digits) == 11 and digits[0] == "1":
            return f"+{digits}"

        # If already has country code format
        if len(digits) >= 10:
            return f"+{digits}"

        # Default: just add +
        return f"+{digits}"

    @staticmethod
    def validate_phone_number(phone: str) -> tuple[bool, str]:
        """
        Validate phone number format

        Args:
            phone: Phone number to validate

        Returns:
            tuple: (is_valid, formatted_number or error_message)
        """
        try:
            from twilio.rest import Client

            if not SMSService._is_twilio_configured():
                return False, "Twilio not configured"

            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

            formatted = SMSService._format_phone_number(phone)

            # Use Twilio's lookup API to validate
            # Note: This incurs a small cost per lookup
            lookup = client.lookups.v1.phone_numbers(formatted).fetch()

            return True, lookup.phone_number

        except Exception as e:
            return False, str(e)
