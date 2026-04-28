"""
Utility functions for user authentication
Handles token generation, validation, and email utilities
"""

import secrets
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken


def generate_activation_token(user):
    """
    Generate a secure activation token for email verification
    Token is stored in Redis with 24-hour expiration
    """
    token = secrets.token_urlsafe(32)
    cache_key = f"activation_token:{token}"

    # Store token in cache for 24 hours
    cache.set(cache_key, str(user.id), timeout=86400)  # 24 hours

    return token


def verify_activation_token(token):
    """
    Verify activation token and return user_id if valid
    Returns None if token is invalid or expired
    """
    cache_key = f"activation_token:{token}"
    user_id = cache.get(cache_key)

    if user_id:
        # Delete token after use (one-time use)
        cache.delete(cache_key)
        return user_id

    return None


def generate_password_reset_token(user):
    """
    Generate a secure password reset token
    Token is stored in Redis with 1-hour expiration
    """
    token = secrets.token_urlsafe(32)
    cache_key = f"password_reset:{token}"

    # Store token in cache for 1 hour
    cache.set(cache_key, str(user.id), timeout=3600)  # 1 hour

    return token


def verify_password_reset_token(token):
    """
    Verify password reset token and return user_id if valid
    Token remains valid until used (then deleted)
    """
    cache_key = f"password_reset:{token}"
    user_id = cache.get(cache_key)

    return user_id  # Don't delete yet - delete after password is reset


def delete_password_reset_token(token):
    """Delete password reset token after use"""
    cache_key = f"password_reset:{token}"
    cache.delete(cache_key)


def generate_jwt_tokens(user):
    """
    Generate JWT access and refresh tokens for user
    """
    refresh = RefreshToken.for_user(user)

    # Add custom claims
    refresh["email"] = user.email
    refresh["user_type"] = user.user_type
    refresh["full_name"] = user.get_full_name()

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def get_activation_url(token):
    """
    Generate activation URL for email
    """
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    return f"{frontend_url}/activate/{token}"


def get_password_reset_url(token):
    """
    Generate password reset URL for email
    """
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    return f"{frontend_url}/reset-password/{token}"


def mask_email(email):
    """
    Mask email for privacy (e.g., j***@example.com)
    """
    if not email:
        return ""

    local, domain = email.split("@")
    if len(local) <= 2:
        masked_local = local[0] + "*" * (len(local) - 1)
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]

    return f"{masked_local}@{domain}"


def is_email_deliverable(email):
    """
    Basic email validation (can be extended with external API)
    """
    # Add your email validation logic here
    # Can integrate with services like ZeroBounce, Hunter.io, etc.
    return True


def rate_limit_key(identifier, action):
    """
    Generate rate limit key for caching
    """
    return f"rate_limit:{action}:{identifier}"


def assert_datetime_with_timezone(dt, field_name="datetime"):
    """
    Assert that a datetime object is timezone-aware
    Raises ValueError if not
    """
    if not dt or not isinstance(dt, datetime):
        raise ValueError(f"Provided value for {field_name} is not a datetime object")

    if timezone.is_naive(dt):
        raise ValueError(f"{field_name} must be timezone-aware")
