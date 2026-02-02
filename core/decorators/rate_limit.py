from django.core.cache import cache
from typing import Callable
import functools
from ..exceptions.base_exceptions import ToManyRequestsError
import re
import time
import logging

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


def rate_limit(key_type: str, rate: str, scope: str = "default"):
    """
    Decorator to apply rate limiting to API views.

    Args:
        key_type: What to track ('ip', 'user_id', or 'email').
        rate: Rate string (e.g., '5/min', '100/day').
        scope: Unique string for the specific action (e.g., 'login', 'create_appointment').
    """

    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            identifier = None

            # 1. Resolve Identifier
            if key_type == "user_id":
                if request.user and request.user.is_authenticated:
                    identifier = str(request.user.id)
            elif key_type == "ip":
                x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
                identifier = (
                    x_forwarded_for.split(",")[0]
                    if x_forwarded_for
                    else request.META.get("REMOTE_ADDR")
                )
            elif key_type == "email":
                identifier = request.data.get("email") or request.query_params.get(
                    "email"
                )

            # Fallback to IP if specific key not found
            if not identifier:
                identifier = request.META.get("REMOTE_ADDR", "unknown")

            # 2. Check Limit
            if RateLimiter.is_limited(identifier, rate, scope):
                logger.warning(f"Rate limit hit for {identifier} on scope {scope}")
                raise RateLimitError(
                    detail=f"Too many requests. Limit is {rate} per {scope}."
                )

            return view_func(self, request, *args, **kwargs)

        return wrapper

    return decorator
