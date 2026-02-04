import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.core.exceptions.base_exceptions import (
    ValidationError,
    NotificationError,
)

from ..models import Notification, NotificationTemplate, NotificationPreference
from .email_service import EmailService
from .sms_service import SMSService
from .push_service import PushService

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationService:
    """Centralized notification orchestration service"""

    @staticmethod
    def create_notification(
        user_id: str,
        template_name: str,
        context: Dict[str, Any],
        channels: Optional[List[str]] = None,
        priority: str = "medium",
        scheduled_for: Optional[datetime] = None,
        **kwargs,
    ) -> Notification:
        """
        Create and queue a notification using a template

        Args:
            user_id: User ID to receive notification
            template_name: Name of notification template
            context: Template context variables
            channels: Override channels (['email', 'sms', 'push'])
            priority: Notification priority
            scheduled_for: When to send (None for immediate)

        Returns:
            Notification object
        """
        try:
            with transaction.atomic():
                # Get user
                user = User.objects.get(user_id=user_id, is_active=True)

                # Get template
                template = NotificationTemplate.objects.get(
                    name=template_name, is_active=True
                )

                # Get user preferences
                preferences, _ = NotificationPreference.objects.get_or_create(
                    user=user,
                    defaults={
                        "email_auth": True,
                        "email_appointments": True,
                        "email_medical": True,
                        "email_billing": True,
                        "email_system": True,
                        "sms_appointments": True,
                    },
                )

                # Determine channels
                if channels is None:
                    channels_to_use = []

                    if template.send_email and preferences.can_receive_notification(
                        template.category, "email"
                    ):
                        channels_to_use.append("email")

                    if (
                        template.send_sms
                        and preferences.can_receive_notification(
                            template.category, "sms"
                        )
                        and user.phone
                    ):
                        channels_to_use.append("sms")

                    if template.send_push and preferences.can_receive_notification(
                        template.category, "push"
                    ):
                        channels_to_use.append("push")
                else:
                    channels_to_use = channels

                # Check if within quiet hours
                if scheduled_for is None and NotificationService._is_quiet_hours(
                    preferences
                ):
                    # Schedule for after quiet hours
                    scheduled_for = NotificationService._get_after_quiet_hours(
                        preferences
                    )

                # Render templates
                rendered = NotificationService._render_templates(template, context)

                # Create notification
                notification = Notification.objects.create(
                    user=user,
                    notification_type=template.notification_type,
                    category=template.category,
                    priority=priority,
                    title=rendered["title"],
                    message=rendered["message"],
                    metadata={
                        "template": template_name,
                        "context": context,
                        "rendered_content": rendered,
                    },
                    send_email="email" in channels_to_use,
                    send_sms="sms" in channels_to_use,
                    send_push="push" in channels_to_use,
                    scheduled_for=scheduled_for,
                    expires_at=(
                        scheduled_for + timedelta(days=7) if scheduled_for else None
                    ),
                    **kwargs,
                )

                # Queue for sending if not scheduled
                if scheduled_for is None:
                    from ..tasks import process_notification

                    process_notification.delay(notification.id)

                logger.info(
                    f"Notification created: {notification.id} - "
                    f"User: {user.email}, Template: {template_name}"
                )

                return notification

        except User.DoesNotExist:
            raise ValidationError(detail="User not found or inactive")
        except NotificationTemplate.DoesNotExist:
            raise ValidationError(detail=f"Template not found: {template_name}")
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e))
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}", exc_info=True)
            raise NotificationError(detail="Failed to create notification")

    @staticmethod
    def send_immediate_notification(
        user_id: str,
        title: str,
        message: str,
        category: str = "system",
        priority: str = "medium",
        channels: Optional[List[str]] = None,
        **kwargs,
    ) -> Notification:
        """
        Send immediate notification without template
        """
        try:
            with transaction.atomic():
                user = User.objects.get(user_id=user_id, is_active=True)

                # Get preferences
                preferences, _ = NotificationPreference.objects.get_or_create(
                    user=user, defaults={"email_system": True}
                )

                # Determine channels
                if channels is None:
                    channels_to_use = []

                    if preferences.email_system:
                        channels_to_use.append("email")

                    if user.phone:
                        channels_to_use.append("sms")
                else:
                    channels_to_use = channels

                # Create notification
                notification = Notification.objects.create(
                    user=user,
                    notification_type=(
                        "email" if "email" in channels_to_use else "in_app"
                    ),
                    category=category,
                    priority=priority,
                    title=title,
                    message=message,
                    send_email="email" in channels_to_use,
                    send_sms="sms" in channels_to_use,
                    send_push="push" in channels_to_use,
                    metadata=kwargs.get("metadata", {}),
                )

                # Send immediately
                from ..tasks import process_notification

                process_notification.delay(notification.id)

                return notification

        except User.DoesNotExist:
            raise ValidationError(detail="User not found")
        except Exception as e:
            logger.error(
                f"Error sending immediate notification: {str(e)}", exc_info=True
            )
            raise NotificationError(detail="Failed to send notification")

    @staticmethod
    def process_notification(notification_id: int) -> bool:
        """
        Process and send a notification through all enabled channels
        """
        try:
            notification = Notification.objects.get(id=notification_id)

            # Check if already processed
            if notification.status in ["sent", "delivered"]:
                return True

            # Update status
            notification.status = "sending"
            notification.save(update_fields=["status", "updated_at"])

            # Send through each channel
            success_channels = []

            if notification.send_email and not notification.email_sent:
                try:
                    EmailService.send_notification_email(notification)
                    success_channels.append("email")
                except Exception as e:
                    logger.error(
                        f"Failed to send email for notification {notification_id}: {str(e)}"
                    )

            if (
                notification.send_sms
                and not notification.sms_sent
                and notification.user.phone
            ):
                try:
                    SMSService.send_notification_sms(notification)
                    success_channels.append("sms")
                except Exception as e:
                    logger.error(
                        f"Failed to send SMS for notification {notification_id}: {str(e)}"
                    )

            if notification.send_push and not notification.push_sent:
                try:
                    PushService.send_notification_push(notification)
                    success_channels.append("push")
                except Exception as e:
                    logger.error(
                        f"Failed to send push for notification {notification_id}: {str(e)}"
                    )

            # Update status
            notification.status = "sent"
            notification.save(update_fields=["status", "updated_at"])

            logger.info(
                f"Notification {notification_id} sent via channels: {success_channels}"
            )

            return len(success_channels) > 0

        except Notification.DoesNotExist:
            logger.error(f"Notification not found: {notification_id}")
            return False
        except Exception as e:
            logger.error(
                f"Error processing notification {notification_id}: {str(e)}",
                exc_info=True,
            )

            # Update notification status
            try:
                notification.status = "failed"
                notification.failure_reason = str(e)[:500]
                notification.save(
                    update_fields=["status", "failure_reason", "updated_at"]
                )
            except:
                pass

            return False

    @staticmethod
    def get_user_notifications(
        user_id: str,
        unread_only: bool = False,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Notification], int]:
        """
        Get user notifications with pagination
        """
        try:
            user = User.objects.get(user_id=user_id)

            queryset = Notification.objects.filter(user=user)

            if unread_only:
                queryset = queryset.filter(is_read=False)

            if category:
                queryset = queryset.filter(category=category)

            total = queryset.count()
            notifications = queryset.order_by("-created_at")[offset : offset + limit]

            return list(notifications), total

        except User.DoesNotExist:
            raise ValidationError(detail="User not found")

    @staticmethod
    def mark_as_read(notification_id: int, user_id: str) -> bool:
        """
        Mark notification as read
        """
        try:
            notification = Notification.objects.get(
                id=notification_id, user__user_id=user_id
            )
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False

    @staticmethod
    def mark_all_as_read(user_id: str) -> int:
        """
        Mark all user notifications as read
        """
        try:
            updated = Notification.objects.filter(
                user__user_id=user_id, is_read=False
            ).update(is_read=True, read_at=timezone.now())
            return updated
        except Exception as e:
            logger.error(f"Error marking all as read: {str(e)}")
            return 0

    # ========== PRIVATE HELPER METHODS ==========

    @staticmethod
    def _render_templates(
        template: NotificationTemplate, context: Dict[str, Any]
    ) -> Dict[str, str]:
        """Render notification templates with context"""
        from django.template import Template, Context

        rendered = {}

        # Render email subject
        email_subject_template = Template(template.email_subject)
        rendered["title"] = email_subject_template.render(Context(context))

        # Render email body
        email_template = Template(template.email_template)
        rendered["message"] = email_template.render(Context(context))

        # Render SMS if template exists
        if template.sms_template:
            sms_template = Template(template.sms_template)
            rendered["sms_message"] = sms_template.render(Context(context))[:500]

        # Render push if template exists
        if template.push_template:
            push_title_template = Template(
                template.push_title or template.email_subject
            )
            push_template = Template(template.push_template)
            rendered["push_title"] = push_title_template.render(Context(context))
            rendered["push_message"] = push_template.render(Context(context))[:200]

        return rendered

    @staticmethod
    def _is_quiet_hours(preferences: NotificationPreference) -> bool:
        """Check if current time is within user's quiet hours"""
        if not preferences.quiet_hours_start or not preferences.quiet_hours_end:
            return False

        from datetime import datetime
        import pytz

        try:
            # Get user's timezone
            user_tz = pytz.timezone(preferences.timezone)
            now = datetime.now(user_tz).time()

            # Check if current time is within quiet hours
            if preferences.quiet_hours_start <= preferences.quiet_hours_end:
                # Normal range (e.g., 10 PM to 8 AM)
                return (
                    preferences.quiet_hours_start <= now <= preferences.quiet_hours_end
                )
            else:
                # Overnight range (e.g., 10 PM to 8 AM)
                return (
                    now >= preferences.quiet_hours_start
                    or now <= preferences.quiet_hours_end
                )

        except pytz.UnknownTimeZoneError:
            return False

    @staticmethod
    def _get_after_quiet_hours(preferences: NotificationPreference) -> datetime:
        """Get datetime after quiet hours end"""
        from datetime import datetime, timedelta
        import pytz

        try:
            user_tz = pytz.timezone(preferences.timezone)
            now = datetime.now(user_tz)

            # Create datetime for quiet hours end today
            end_time_today = datetime.combine(now.date(), preferences.quiet_hours_end)
            end_time_today = user_tz.localize(end_time_today)

            # If quiet hours end is before now, it means quiet hours end tomorrow
            if end_time_today < now:
                end_time_today += timedelta(days=1)

            return end_time_today

        except pytz.UnknownTimeZoneError:
            # Fallback to 2 hours from now
            return timezone.now() + timedelta(hours=2)
