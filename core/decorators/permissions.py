import functools
import logging
from typing import Callable, Any, List, Union
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework import status

from core.responses.api_response import APIResponse
from core.exceptions.base_exceptions import AuthorizationError

logger = logging.getLogger(__name__)
User = get_user_model()


def user_is_authenticated(view_func: Callable) -> Callable:
    """
    Decorator to ensure user is authenticated.
    Basic wrapper that can be used with other decorators.
    """

    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise AuthorizationError(
                detail="Authentication required", code="authentication_required"
            )
        return view_func(self, request, *args, **kwargs)

    return wrapper


def user_is_active(view_func: Callable) -> Callable:
    """
    Decorator to ensure user account is active.
    """

    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_active:
            raise AuthorizationError(
                detail="Account is inactive", code="account_inactive"
            )
        return view_func(self, request, *args, **kwargs)

    return wrapper


def user_is_patient(view_func: Callable) -> Callable:
    """
    Decorator to check if the user is a patient.
    Automatically checks authentication and active status.
    """

    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise AuthorizationError(
                detail="Authentication required", code="authentication_required"
            )

        if not request.user.is_active:
            raise AuthorizationError(
                detail="Account is inactive", code="account_inactive"
            )

        if request.user.user_type != "patient":
            raise AuthorizationError(
                detail="This endpoint is only accessible to patients",
                code="patient_required",
            )

        return view_func(self, request, *args, **kwargs)

    return wrapper


def user_is_specialist(view_func: Callable) -> Callable:
    """
    Decorator to check if the user is a specialist.
    Also verifies the specialist profile exists.
    """

    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise AuthorizationError(
                detail="Authentication required", code="authentication_required"
            )

        if not request.user.is_active:
            raise AuthorizationError(
                detail="Account is inactive", code="account_inactive"
            )

        if request.user.user_type != "specialist":
            raise AuthorizationError(
                detail="This endpoint is only accessible to specialists",
                code="specialist_required",
            )

        try:
            from apps.specialists.models import Specialist

            if not hasattr(request.user, "specialist_profile"):
                raise AuthorizationError(
                    detail="Specialist profile not found",
                    code="specialist_profile_missing",
                )
        except ImportError:
            # Specialist app not installed, skip profile check
            pass

        return view_func(self, request, *args, **kwargs)

    return wrapper


def user_is_admin(view_func: Callable) -> Callable:
    """
    Decorator to check if the user is an admin.
    Checks both user_type and is_staff flag.
    """

    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise AuthorizationError(
                detail="Authentication required", code="authentication_required"
            )

        if not request.user.is_active:
            raise AuthorizationError(
                detail="Account is inactive", code="account_inactive"
            )

        if request.user.user_type != "admin" or not request.user.is_staff:
            raise AuthorizationError(
                detail="This endpoint is only accessible to administrators",
                code="admin_required",
            )

        return view_func(self, request, *args, **kwargs)

    return wrapper


def user_is_staff(view_func: Callable) -> Callable:
    """
    Decorator to check if the user is staff (admin or staff).
    """

    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise AuthorizationError(
                detail="Authentication required", code="authentication_required"
            )

        if not request.user.is_active:
            raise AuthorizationError(
                detail="Account is inactive", code="account_inactive"
            )

        if not request.user.is_staff:
            raise AuthorizationError(
                detail="This endpoint is only accessible to staff members",
                code="staff_required",
            )

        return view_func(self, request, *args, **kwargs)

    return wrapper


def user_is_admin_or_staff(view_func: Callable) -> Callable:
    """
    Decorator to check if the user is admin or staff.
    Combines admin and staff permissions.
    """

    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise AuthorizationError(
                detail="Authentication required", code="authentication_required"
            )

        if not request.user.is_active:
            raise AuthorizationError(
                detail="Account is inactive", code="account_inactive"
            )

        is_admin = request.user.user_type == "admin"
        is_staff_user = request.user.user_type == "staff"

        if not (is_admin or is_staff_user or request.user.is_staff):
            raise AuthorizationError(
                detail="This endpoint is only accessible to administrators or staff",
                code="admin_or_staff_required",
            )

        return view_func(self, request, *args, **kwargs)

    return wrapper


def require_permissions(permission_decorators: List[Callable]) -> Callable:
    """
    Meta-decorator to require multiple permissions (OR logic).
    User must satisfy at least one of the provided permission decorators.

    Usage:
        @require_permissions([user_is_admin, user_is_specialist])
        def my_view(request):
            # Accessible to admins OR specialists
            pass
    """

    def decorator(view_func: Callable) -> Callable:

        @functools.wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            # Track if any permission passed
            permission_granted = False
            last_exception = None

            # Try each permission decorator
            for permission_decorator in permission_decorators:
                try:
                    # Create a test wrapper with the permission decorator
                    test_wrapper = permission_decorator(lambda *a, **kw: None)
                    test_wrapper(self, request, *args, **kwargs)

                    # If no exception was raised, permission is granted
                    permission_granted = True
                    break

                except AuthorizationError as e:
                    last_exception = e
                    continue
                except Exception as e:
                    # Log unexpected errors but continue
                    logger.warning(f"Unexpected error in permission check: {str(e)}")
                    last_exception = e
                    continue

            # If no permission was granted, raise the last exception
            if not permission_granted and last_exception:
                raise last_exception

            # If permission was granted, execute the view
            return view_func(self, request, *args, **kwargs)

        return wrapper

    return decorator


def owns_appointment(view_func: Callable) -> Callable:
    """
    Decorator to check if the user owns the appointment.
    Assumes the view has 'appointment_id' in kwargs.
    """

    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        appointment_id = kwargs.get("appointment_id")
        if not appointment_id:
            raise AuthorizationError(
                detail="Appointment ID not provided", code="appointment_id_missing"
            )

        from apps.appointments.models import Appointment

        try:
            appointment = Appointment.objects.get(id=appointment_id)
        except Appointment.DoesNotExist:
            raise AuthorizationError(
                detail="Appointment not found", code="appointment_not_found"
            )

        if appointment.patient.user != request.user:
            raise AuthorizationError(
                detail="You do not have permission to access this appointment",
                code="appointment_ownership_required",
            )

        return view_func(self, request, *args, **kwargs)

    return wrapper
