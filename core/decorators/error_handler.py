import functools
import logging
from typing import Callable, Any
from django.db import transaction, DatabaseError
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework import status

from core.exceptions.base_exceptions import (
    MindCareBaseException,
    DatabaseError as MindCareDatabaseError,
)
from core.responses.api_response import APIResponse

logger = logging.getLogger(__name__)


def api_error_handler(view_func: Callable) -> Callable:
    """
    Decorator for the centralized error handling in API views.
    Catches known exceptions and returns standardized API responses.

    Examples of usage:
    @api_error_handler
    def my_view(self, request, *args, **kwargs) -> Response:
        ...
    """

    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        try:
            return view_func(self, request, *args, **kwargs)

        except MindCareBaseException as e:
            log_level = getattr(e, "log_level", "warning")
            # Convert string log level to integer if needed
            if isinstance(log_level, str):
                log_level = getattr(logging, log_level.upper(), logging.WARNING)

            logger.log(
                log_level,
                f"{e.__class__.__name__}: {e.detail}",
                extra={"metadata": getattr(e, "metadata", {})},
            )

            return APIResponse.error(
                message=str(e.detail),
                code=getattr(e, "default_code", "error"),
                status_code=e.status_code,
                metadata=getattr(e, "metadata", {}),
            )

        except DRFValidationError as e:
            # DRF validation errors
            logger.warning(f"Validation error: {e.detail}")
            return APIResponse.error(
                message="Validation failed",
                errors=e.detail,
                code="validation_error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        except DjangoValidationError as e:
            # Django validation errors
            logger.warning(f"Django validation error: {e.message}")
            return APIResponse.error(
                message=str(e.message),
                code="validation_error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        except DatabaseError as e:
            # Database errors
            logger.error(f"Database error: {str(e)}", exc_info=True)
            return APIResponse.error(
                message="A database error occurred",
                code="database_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception as e:
            # Unexpected errors
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return APIResponse.error(
                message="An unexpected error occurred",
                code="unexpected_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    return wrapper


def atomic_transaction(view_func: Callable) -> Callable:
    """
    Decorator to execute a view within a database transaction
    with rollback error handling.
    """

    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                return view_func(self, request, *args, **kwargs)

        except Exception as e:
            # If an error occurs, the transaction has already rolled back
            logger.error(f"Transaction failed and rolled back: {str(e)}", exc_info=True)
            raise MindCareDatabaseError(
                detail="Operation could not be completed due to a database error",
                metadata={"original_error": str(e)},
            )

    return wrapper


def require_http_methods(methods: list):
    """
    Decorator to restrict HTTP methods
    """

    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            if request.method not in methods:
                return APIResponse.error(
                    message=f"Method {request.method} not allowed",
                    code="method_not_allowed",
                    status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                )
            return view_func(self, request, *args, **kwargs)

        return wrapper

    return decorator


def rate_limit(key: str, rate: str, scope: str = "default"):
    """
    Decorator to apply rate limiting to API views.
    This is a placeholder implementation; actual rate limiting logic
    should be integrated with a library like django-ratelimit or similar.
    """

    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            # Placeholder for rate limiting logic
            # In a real implementation, check if the request exceeds the rate limit
            # If exceeded, raise RateLimitError

            # Example:
            # if is_rate_limited(key, rate, scope):
            #     raise RateLimitError(detail="Rate limit exceeded")

            return view_func(self, request, *args, **kwargs)

        return wrapper

    return decorator
