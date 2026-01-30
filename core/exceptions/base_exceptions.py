from rest_framework import status
from rest_framework.exceptions import APIException


class MindCareBaseException(APIException):
    """Base exception for MindCare application."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "An error occurred"
    default_code = "error"
    log_level = "error"

    def __init__(self, detail=None, code=None, metadata=None):
        super().__init__(detail=detail, code=code)
        self.metadata = metadata or {}


# Authentication & Authorization
class AuthenticationError(MindCareBaseException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Authentication failed"
    default_code = "authentication_error"


class AuthorizationError(MindCareBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to perform this action"
    default_code = "authorization_error"


class PrivacyError(MindCareBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Privacy violation detected"
    default_code = "privacy_error"


class TokenError(AuthenticationError):
    default_detail = "Invalid or expired token"
    default_code = "token_error"


# Validation
class ValidationError(MindCareBaseException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Validation error"
    default_code = "validation_error"


class NotFoundError(MindCareBaseException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Resource not found"
    default_code = "not_found"


class BusinessRuleError(MindCareBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Business rule violation"
    default_code = "business_rule_violation"


class PaymentError(MindCareBaseException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "Payment processing error"
    default_code = "payment_error"


class ConflictError(MindCareBaseException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict error"
    default_code = "conflict_error"


class UserNotFoundError(ValidationError):
    default_detail = "User not found"
    default_code = "user_not_found"


class NotificationError(MindCareBaseException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Notification error"
    default_code = "notification_error"


# Rate Limiting
class RateLimitError(MindCareBaseException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many requests"
    default_code = "rate_limit_exceeded"

    def __init__(self, retry_after=None, **kwargs):
        super().__init__(**kwargs)
        self.retry_after = retry_after
        self.headers = {"Retry-After": str(retry_after)} if retry_after else {}


# Business Logic
class UserAlreadyActiveError(ValidationError):
    default_detail = "User account is already active"
    default_code = "user_already_active"


class InvalidResetTokenError(ValidationError):
    default_detail = "Invalid or expired reset token"
    default_code = "invalid_reset_token"


# Database
class DatabaseError(MindCareBaseException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Database operation failed"
    default_code = "database_error"


# External Services
class EmailServiceError(MindCareBaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Email service is temporarily unavailable"
    default_code = "email_service_error"


class PaymentServiceError(MindCareBaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Payment service is temporarily unavailable"
    default_code = "payment_service_error"
