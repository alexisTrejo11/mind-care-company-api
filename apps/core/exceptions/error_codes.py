from enum import Enum


class ErrorCode(Enum):
    # Authentication (AUTH_xxx)
    AUTH_INVALID_CREDENTIALS = "AUTH_001"
    AUTH_TOKEN_EXPIRED = "AUTH_002"
    AUTH_TOKEN_INVALID = "AUTH_003"
    AUTH_ACCOUNT_INACTIVE = "AUTH_004"
    AUTH_RATE_LIMITED = "AUTH_005"

    # Validation (VAL_xxx)
    VAL_REQUIRED_FIELD = "VAL_001"
    VAL_INVALID_EMAIL = "VAL_002"
    VAL_INVALID_PASSWORD = "VAL_003"
    VAL_PASSWORD_MISMATCH = "VAL_004"
    VAL_INVALID_PHONE = "VAL_005"

    # User (USER_xxx)
    USER_NOT_FOUND = "USER_001"
    USER_ALREADY_EXISTS = "USER_002"
    USER_INACTIVE = "USER_003"
    USER_ALREADY_ACTIVE = "USER_004"

    # Business Logic (BIZ_xxx)
    BIZ_APPOINTMENT_CONFLICT = "BIZ_001"
    BIZ_SPECIALIST_UNAVAILABLE = "BIZ_002"
    BIZ_INSUFFICIENT_PERMISSIONS = "BIZ_003"

    # System (SYS_xxx)
    SYS_DATABASE_ERROR = "SYS_001"
    SYS_EXTERNAL_SERVICE = "SYS_002"
    SYS_UNEXPECTED_ERROR = "SYS_003"


ERROR_FRIENDLY_MESSAGES = {
    # Authentication errors
    ErrorCode.AUTH_INVALID_CREDENTIALS: "Invalid email or password",
    ErrorCode.AUTH_TOKEN_EXPIRED: "Your session has expired. Please log in again.",
    ErrorCode.AUTH_TOKEN_INVALID: "Invalid authentication token",
    ErrorCode.AUTH_ACCOUNT_INACTIVE: "Your account is inactive. Please contact support.",
    ErrorCode.AUTH_RATE_LIMITED: "Too many requests. Please try again later.",
    # Validation errors
    ErrorCode.VAL_REQUIRED_FIELD: "Required field is missing",
    ErrorCode.VAL_INVALID_EMAIL: "The email address provided is not valid",
    ErrorCode.VAL_INVALID_PASSWORD: "Password does not meet requirements",
    ErrorCode.VAL_PASSWORD_MISMATCH: "Passwords do not match",
    ErrorCode.VAL_INVALID_PHONE: "Invalid phone number format",
    # User errors
    ErrorCode.USER_NOT_FOUND: "User not found",
    ErrorCode.USER_ALREADY_EXISTS: "User with this email already exists",
    ErrorCode.USER_INACTIVE: "User account is inactive",
    ErrorCode.USER_ALREADY_ACTIVE: "User account is already active",
    # Business logic errors
    ErrorCode.BIZ_APPOINTMENT_CONFLICT: "The selected time slot is not available",
    ErrorCode.BIZ_SPECIALIST_UNAVAILABLE: "Specialist is not available at this time",
    ErrorCode.BIZ_INSUFFICIENT_PERMISSIONS: "You don't have permission to perform this action",
    # System errors
    ErrorCode.SYS_DATABASE_ERROR: "A database error occurred. Please try again.",
    ErrorCode.SYS_EXTERNAL_SERVICE: "External service is currently unavailable",
    ErrorCode.SYS_UNEXPECTED_ERROR: "An unexpected error occurred. Please try again.",
}
