from django.core.cache import cache
from typing import Callable, Dict, Optional, Union
import functools
from ..exceptions.base_exceptions import ToManyRequestsError
import re
import time
import logging
from .profiles import RateLimitProfiles

logger = logging.getLogger(__name__)


class RateLimitError(ToManyRequestsError):
    default_detail = "Rate limit exceeded"
    default_code = "rate_limit_exceeded"

    def __init__(
        self, detail="Too many requests", retry_after=None, code=None, metadata=None
    ):
        super().__init__(detail, code, metadata)
        self.retry_after = retry_after


class RateLimiter:
    """
    Redis-based sliding window rate limiter using Django's cache abstraction.
    Works best with 'django-redis' backend.
    """

    @staticmethod
    def parse_rate(rate: str):
        """
        Parses rate string like "5/15min" into (5, 900) where 900 is seconds.
        Return (limit, period_in_seconds)
        """
        match = re.match(r"(\d+)\/(\d+)?(sec|min|hr|day)", rate)
        if not match:
            logger.error(f"Invalid rate limit format: {rate}. Falling back to 5/min.")
            return 5, 60

        count = int(match.group(1))
        value = int(match.group(2)) if match.group(2) else 1
        unit = match.group(3)

        multipliers_in_secs = {
            "sec": 1,
            "min": 60,
            "hr": 3600,
            "day": 86400,
        }

        return count, value * multipliers_in_secs[unit]

    @classmethod
    def is_limited(cls, key: str, rate: str, scope: str) -> bool:
        """
        Checks if the request exceeds the rate limit.
        Uses a sliding window algorithm with Django's cache.
        """
        limit, period = cls.parse_rate(rate)
        now = time.time()

        cache_key = f"rate_limit:{scope}:{key}"

        history = cache.get(cache_key, [])

        cutoff = now - period
        history = [t for t in history if t > cutoff]

        if len(history) >= limit:
            return True

        history.append(now)
        cache.set(cache_key, history, timeout=period)
        return False


def rate_limit(
    profile: Optional[str] = None,
    key_type: Optional[str] = None,
    rate: Optional[str] = None,
    scope: str = "default",
):
    """
    Decorator to apply rate limiting to API views.

    Can be used in two ways:
    1. With a predefined profile:
       @rate_limit(profile="SENSITIVE", scope="login")

    2. With explicit parameters (legacy):
       @rate_limit(key_type="email", rate="5/min", scope="login")

    Args:
        profile: Name of predefined rate limit profile (e.g., 'SENSITIVE', 'STANDARD').
        key_type: What to track ('ip', 'user_id', or 'email'). Required if not using profile.
        rate: Rate string (e.g., '5/min', '100/day'). Required if not using profile.
        scope: Unique string for the specific action (e.g., 'login', 'create_appointment').

    Raises:
        ValueError: If neither profile nor (key_type and rate) are provided.
    """

    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            # Resolve rate limit configuration
            if profile:
                try:
                    config = RateLimitProfiles.get_profile(profile)
                    resolved_key_type = config["key_type"]
                    resolved_rate = config["rate"]
                except ValueError as e:
                    logger.error(f"Invalid rate limit profile: {e}")
                    raise
            elif key_type and rate:
                resolved_key_type = key_type
                resolved_rate = rate
            else:
                raise ValueError(
                    "Either 'profile' or both 'key_type' and 'rate' must be provided"
                )

            identifier = None

            # 1. Resolve Identifier
            if resolved_key_type == "user_id":
                if request.user and request.user.is_authenticated:
                    identifier = str(request.user.id)
            elif resolved_key_type == "ip":
                x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
                identifier = (
                    x_forwarded_for.split(",")[0]
                    if x_forwarded_for
                    else request.META.get("REMOTE_ADDR")
                )
            elif resolved_key_type == "email":
                identifier = request.data.get("email") or request.query_params.get(
                    "email"
                )

            # Fallback to IP if specific key not found
            if not identifier:
                identifier = request.META.get("REMOTE_ADDR", "unknown")

            # 2. Check Limit
            if RateLimiter.is_limited(identifier, resolved_rate, scope):
                logger.warning(f"Rate limit hit for {identifier} on scope {scope}")
                raise RateLimitError(
                    detail=f"Too many requests. Limit is {resolved_rate} per {scope}."
                )

            return view_func(self, request, *args, **kwargs)

        return wrapper

    return decorator
