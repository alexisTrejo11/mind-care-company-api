from django.core.cache import cache
from functools import wraps
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


def cache_method(timeout_in_secs=900, key_prefix=None, version=None):
    """
    Decorator to cache the result of a method call.

    :param timeout: Time in seconds to cache the result (default: 900 seconds or 15 minutes)
    :param key_prefix: Prefix to use for the cache key (optional)
    :param version: Version of the cache key (optional)
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key_parts = [
                key_prefix or func.module + "." + func.__name__,
                str(version) if version else None,
            ]

            # Include arguments exclude self cause is a static method
            if args:
                start_idx = 1 if args and hasattr(args[0], "__class__") else 0
                cache_key_parts.extend(str(arg) for arg in args[start_idx:])
            if kwargs:
                cache_key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))

            cache_key = hashlib.md5(
                json.dumps(cache_key_parts, sort_keys=True).encode()
            ).hexdigest()

            result = cache.get(cache_key)
            if result is not None:
                logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                return result

            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout=timeout_in_secs)
            logger.debug(f"Cache set for {func.__name__}: {cache_key}")

            return result

        return wrapper

    return decorator
