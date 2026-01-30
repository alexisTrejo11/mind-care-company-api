# apps/billing/tasks.py
"""
Celery tasks for billing system
"""
from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from .models import Bill, Payment
from .services import BillingService
from apps.notification.tasks import send_notification

logger = get_task_logger(__name__)


@shared_task
def send_payment_reminders():
    """
    Send payment reminders for overdue and upcoming due bills
    Runs daily
    """
    try:
        today = timezone.now().date()

        # Bills due in 3 days
        upcoming_due_date = today + timedelta(days=3)
        upcoming_bills = Bill.objects.filter(
            payment_status__in=["pending", "partial"],
            due_date=upcoming_due_date,
        ).select_related("patient")

        for bill in upcoming_bills:
            send_notification.delay(
                template_name="payment_upcoming_reminder",
                user_id=str(bill.patient.user_id),
                context={
                    "bill_number": bill.bill_number,
                    "total_amount": float(bill.total_amount),
                    "balance_due": float(bill.balance_due),
                    "due_date": bill.due_date.isoformat(),
                    "payment_url": bill.get_payment_url(),
                },
            )

        # Overdue bills (30, 60, 90 days)
        overdue_periods = [30, 60, 90]

        for days in overdue_periods:
            overdue_date = today - timedelta(days=days)
            overdue_bills = Bill.objects.filter(
                payment_status="overdue",
                due_date=overdue_date,
            ).select_related("patient")

            for bill in overdue_bills:
                send_notification.delay(
                    template_name=f"payment_overdue_{days}_days",
                    user_id=str(bill.patient.user_id),
                    context={
                        "bill_number": bill.bill_number,
                        "balance_due": float(bill.balance_due),
                        "days_overdue": days,
                        "due_date": bill.due_date.isoformat(),
                        "payment_url": bill.get_payment_url(),
                    },
                )

        logger.info(
            f"Sent payment reminders: {upcoming_bills.count()} upcoming, "
            f"{overdue_bills.count()} overdue"
        )

        return {
            "upcoming_reminders": upcoming_bills.count(),
            "overdue_reminders": overdue_bills.count(),
        }

    except Exception as e:
        logger.error(f"Error sending payment reminders: {str(e)}", exc_info=True)
        return {"error": str(e)}


@shared_task
def update_overdue_bills():
    """
    Update bill status to overdue
    Runs daily
    """
    try:
        today = timezone.now().date()

        # Find bills that are due but not paid
        bills_to_update = Bill.objects.filter(
            payment_status__in=["pending", "partial"],
            due_date__lt=today,
        )

        updated_count = bills_to_update.update(
            payment_status="overdue",
            invoice_status="overdue",
            updated_at=timezone.now(),
        )

        logger.info(f"Updated {updated_count} bills to overdue status")

        return {"updated_count": updated_count}

    except Exception as e:
        logger.error(f"Error updating overdue bills: {str(e)}", exc_info=True)
        return {"error": str(e)}


@shared_task
def generate_monthly_statistics():
    """
    Generate monthly billing statistics report
    Runs monthly
    """
    try:
        from datetime import datetime

        # Get last month
        today = timezone.now()
        first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last_day_last_month = today.replace(day=1) - timedelta(days=1)

        # Generate statistics
        stats = BillingService.get_billing_statistics(
            start_date=first_day_last_month,
            end_date=last_day_last_month,
        )

        # Send report to admins
        from django.contrib.auth import get_user_model

        User = get_user_model()

        admins = User.objects.filter(user_type="admin", is_active=True)

        for admin in admins:
            send_notification.delay(
                template_name="monthly_billing_report",
                user_id=str(admin.user_id),
                context={
                    "month": first_day_last_month.strftime("%B %Y"),
                    "stats": stats,
                    "report_date": today.date().isoformat(),
                },
            )

        logger.info(
            f'Generated monthly statistics for {first_day_last_month.strftime("%B %Y")}'
        )

        return {
            "month": first_day_last_month.strftime("%B %Y"),
            "stats_generated": True,
        }

    except Exception as e:
        logger.error(f"Error generating monthly statistics: {str(e)}", exc_info=True)
        return {"error": str(e)}


@shared_task(bind=True, max_retries=3)
def process_recurring_payments(self):
    """
    Process recurring payments for subscription-based services
    Runs daily
    """
    # This would process recurring payments for subscription services
    # Implementation depends on your business model

    logger.info("Recurring payments processing started")

    # Placeholder for recurring payment logic
    # In production, this would:
    # 1. Find subscriptions due for payment
    # 2. Create bills for each subscription
    # 3. Process payments via Stripe
    # 4. Send notifications

    return {"processed": 0, "message": "Recurring payments processing not implemented"}
