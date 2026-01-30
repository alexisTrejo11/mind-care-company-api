"""
Celery tasks for centralized notification system
"""

from celery import shared_task, group, chain
from celery.utils.log import get_task_logger
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from .models import Notification
from .services.notification_service import NotificationService

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification(self, template_name: str, user_id: str, context: dict, **kwargs):
    """
    Send a notification using template

    Usage from other apps:
        from apps.notifications.tasks import send_notification

        send_notification.delay(
            template_name='user_welcome',
            user_id=str(user.user_id),
            context={
                'user_name': user.get_full_name(),
                'activation_url': activation_url,
            }
        )
    """
    try:
        notification = NotificationService.create_notification(
            user_id=user_id, template_name=template_name, context=context, **kwargs
        )

        return {
            "status": "queued",
            "notification_id": notification.id,
            "user_id": user_id,
            "template": template_name,
        }

    except Exception as exc:
        logger.error(f"Failed to queue notification: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_immediate_notification(self, title: str, message: str, user_id: str, **kwargs):
    """
    Send immediate notification without template
    """
    try:
        notification = NotificationService.send_immediate_notification(
            user_id=user_id, title=title, message=message, **kwargs
        )

        return {
            "status": "sent",
            "notification_id": notification.id,
            "user_id": user_id,
        }

    except Exception as exc:
        logger.error(f"Failed to send immediate notification: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task(bind=True, max_retries=3)
def process_notification(self, notification_id: int):
    """
    Process and send a specific notification
    """
    try:
        success = NotificationService.process_notification(notification_id)

        return {
            "notification_id": notification_id,
            "success": success,
            "processed_at": timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"Failed to process notification {notification_id}: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task
def process_pending_notifications():
    """
    Process all pending notifications (cron job)
    """
    try:
        now = timezone.now()

        # Get notifications scheduled for now or earlier
        pending_notifications = Notification.objects.filter(
            status__in=["pending", "queued"],
            scheduled_for__lte=now,
            expires_at__gte=now,  # Not expired
            retry_count__lt=models.F("max_retries"),  # Not exceeded max retries
        ).select_related("user")[
            :100
        ]  # Limit batch size

        notification_ids = list(pending_notifications.values_list("id", flat=True))

        if not notification_ids:
            logger.info("No pending notifications to process")
            return {"processed": 0}

        # Update status to queued
        Notification.objects.filter(id__in=notification_ids).update(
            status="queued", updated_at=now
        )

        # Process in parallel
        tasks = [process_notification.s(notif_id) for notif_id in notification_ids]
        job = group(tasks)
        result = job.apply_async()

        logger.info(f"Processing {len(notification_ids)} pending notifications")

        return {
            "processed": len(notification_ids),
            "task_group_id": result.id,
            "notification_ids": notification_ids,
        }

    except Exception as e:
        logger.error(f"Error processing pending notifications: {str(e)}", exc_info=True)
        return {"error": str(e)}
