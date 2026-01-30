"""
Celery Tasks for User Authentication
Handles asynchronous email sending for activation, welcome, and password reset
"""

from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_activation_email(self, user_id, user_email, user_name, activation_token):
    """
    Send account activation email to user
    """
    try:
        from core.shared import get_activation_url

        activation_url = get_activation_url(activation_token)

        email_context = {
            "user_name": user_name,
            "activation_url": activation_url,
            "site_name": "MindCare Hub",
            "support_email": settings.DEFAULT_FROM_EMAIL,
        }

        # Render HTML email
        html_content = render_to_string(
            "users/emails/activation_email.html", email_context
        )
        text_content = strip_tags(html_content)

        # Create email
        subject = "Activate Your MindCare Hub Account"
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email],
        )
        email.attach_alternative(html_content, "text/html")

        # Send email
        email.send()

        logger.info(f"Activation email sent to {user_email}")
        return f"Activation email sent successfully to {user_email}"
    except Exception as exc:
        logger.error(f"Failed to send activation email to {user_email}: {str(exc)}")
        # Retry task with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, user_id, user_email, user_name):
    """
    Send welcome email after successful account activation
    """
    try:
        # Email context
        context = {
            "user_name": user_name,
            "site_name": "MindCare Hub",
            "login_url": f"{settings.FRONTEND_URL}/login",
            "dashboard_url": f"{settings.FRONTEND_URL}/dashboard",
            "support_email": settings.DEFAULT_FROM_EMAIL,
        }

        # Render HTML email
        html_content = render_to_string("users/emails/welcome_email.html", context)
        text_content = strip_tags(html_content)

        # Create email
        subject = "Welcome to MindCare Hub!"
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email],
        )
        email.attach_alternative(html_content, "text/html")

        # Send email
        email.send()

        logger.info(f"Welcome email sent to {user_email}")
        return f"Welcome email sent successfully to {user_email}"

    except Exception as exc:
        logger.error(f"Failed to send welcome email to {user_email}: {str(exc)}")
        # Retry task with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_password_reset_email(self, user_email, user_name, reset_token):
    """
    Send password reset email to user
    """
    try:
        from core.shared import get_password_reset_url

        reset_url = get_password_reset_url(reset_token)

        # Email context
        context = {
            "user_name": user_name,
            "reset_url": reset_url,
            "site_name": "MindCare Hub",
            "support_email": settings.DEFAULT_FROM_EMAIL,
            "valid_hours": 1,  # Token valid for 1 hour
        }

        # Render HTML email
        html_content = render_to_string(
            "users/emails/password_reset_email.html", context
        )
        text_content = strip_tags(html_content)

        # Create email
        subject = "Reset Your MindCare Hub Password"
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email],
        )
        email.attach_alternative(html_content, "text/html")

        # Send email
        email.send()

        logger.info(f"Password reset email sent to {user_email}")
        return f"Password reset email sent successfully to {user_email}"

    except Exception as exc:
        logger.error(f"Failed to send password reset email to {user_email}: {str(exc)}")
        # Retry task with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_password_changed_notification(self, user_email, user_name):
    """
    Send notification email when password is successfully changed
    """
    try:
        # Email context
        context = {
            "user_name": user_name,
            "site_name": "MindCare Hub",
            "support_email": settings.DEFAULT_FROM_EMAIL,
            "security_url": f"{settings.FRONTEND_URL}/account/security",
        }

        # Render HTML email
        html_content = render_to_string(
            "users/emails/password_changed_email.html", context
        )
        text_content = strip_tags(html_content)

        # Create email
        subject = "Your MindCare Hub Password Was Changed"
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email],
        )
        email.attach_alternative(html_content, "text/html")

        # Send email
        email.send()

        logger.info(f"Password change notification sent to {user_email}")
        return f"Password change notification sent successfully to {user_email}"

    except Exception as exc:
        logger.error(
            f"Failed to send password change notification to {user_email}: {str(exc)}"
        )
        # Retry task with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task
def cleanup_expired_tokens():
    """
    Periodic task to cleanup expired tokens from cache
    This is handled automatically by Redis TTL, but can be used for additional cleanup
    """
    logger.info("Token cleanup task executed")
    return "Token cleanup completed"
