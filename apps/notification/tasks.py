"""
Celery tasks for centralized notification system
"""

from celery import shared_task, group, chain
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.db.models import F
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
    logger.info(
        f"Queuing notification for user {user_id} with template {template_name}"
    )
    try:
        notification = NotificationService.create_notification(
            user_id=user_id, template_name=template_name, context=context, **kwargs
        )

        result = {
            "status": "queued",
            "notification_id": notification.id,
            "user_id": user_id,
            "template": template_name,
        }
        logger.info(f"Notification queued successfully: {result}")
        return result

    except Exception as exc:
        logger.error(f"Failed to queue notification: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_immediate_notification(self, title: str, message: str, user_id: str, **kwargs):
    """
    Send immediate notification without template

    Usage:
        send_immediate_notification.delay(
            title='Quick Alert',
            message='Your appointment is in 1 hour',
            user_id=str(user.user_id),
            category='appointment',
            priority='high'
        )
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

    This task handles the actual sending through configured channels (email, SMS, push)
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

    Scheduled to run every 5 minutes via Celery Beat
    Processes notifications that are:
    - Scheduled for now or earlier
    - Not expired
    - Haven't exceeded max retries
    """
    try:
        now = timezone.now()

        # Get notifications scheduled for now or earlier
        pending_notifications = (
            Notification.objects.filter(
                status__in=["pending", "queued"],
                retry_count__lt=F("max_retries"),  # Not exceeded max retries
            )
            .filter(
                # Either scheduled for now/past, or not scheduled at all
                models.Q(scheduled_for__lte=now)
                | models.Q(scheduled_for__isnull=True)
            )
            .exclude(
                # Exclude expired notifications
                expires_at__lt=now
            )
            .select_related("user")[:100]
        )  # Limit batch size

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


@shared_task
def cleanup_old_notifications():
    """
    Clean up old read notifications (optional maintenance task)

    Runs weekly to delete read notifications older than 90 days
    Keeps unread notifications indefinitely
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=90)

        deleted_count, _ = Notification.objects.filter(
            is_read=True, created_at__lt=cutoff_date
        ).delete()

        logger.info(f"Deleted {deleted_count} old read notifications")

        return {"deleted": deleted_count, "cutoff_date": cutoff_date.isoformat()}

    except Exception as e:
        logger.error(f"Error cleaning up notifications: {str(e)}", exc_info=True)
        return {"error": str(e)}


@shared_task
def send_bulk_notifications(
    user_ids: list, template_name: str, context: dict, **kwargs
):
    """
    Send the same notification to multiple users

    Usage:
        send_bulk_notifications.delay(
            user_ids=['uuid1', 'uuid2', 'uuid3'],
            template_name='system_maintenance',
            context={'maintenance_date': '2024-03-15'}
        )
    """
    try:
        results = {"total": len(user_ids), "success": 0, "failed": 0, "errors": []}

        for user_id in user_ids:
            try:
                send_notification.delay(
                    template_name=template_name,
                    user_id=user_id,
                    context=context,
                    **kwargs,
                )
                results["success"] += 1

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"user_id": user_id, "error": str(e)})
                logger.error(
                    f"Failed to queue notification for user {user_id}: {str(e)}"
                )

        logger.info(
            f"Bulk notifications queued - "
            f"Success: {results['success']}, Failed: {results['failed']}"
        )

        return results

    except Exception as e:
        logger.error(f"Error in bulk notifications: {str(e)}", exc_info=True)
        return {"error": str(e)}


# Import models at module level to fix the NameError
from django.db import models
