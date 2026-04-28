import logging
import re
from django.db import transaction
from django.apps import apps


class InfoOnlyFilter(logging.Filter):
    """Filter to only pass INFO level logs"""

    def filter(self, record):
        return record.levelno == logging.INFO


class ExcludeSensitiveFilter(logging.Filter):
    """
    Filter sensitive data from logs to prevent leaking credentials,
    credit cards, SSNs, and other sensitive information.
    """

    SENSITIVE_PATTERNS = [
        # Authentication
        (r"password[^=]*=([^&\s]+)", "[FILTERED_PASSWORD]"),
        (r"token[^=]*=([^&\s]+)", "[FILTERED_TOKEN]"),
        (r"api[_-]?key[^=]*=([^&\s]+)", "[FILTERED_API_KEY]"),
        (r"secret[^=]*=([^&\s]+)", "[FILTERED_SECRET]"),
        (r"bearer\s+([a-zA-Z0-9\-._~+/]+)", "bearer [FILTERED_TOKEN]"),
        # Financial
        (r"credit[_-]?card[^=]*=([^&\s]+)", "[FILTERED_CC]"),
        (r"cc[_-]?number[^=]*=([^&\s]+)", "[FILTERED_CC]"),
        (r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b", "[FILTERED_CC_NUMBER]"),
        (r"cvv[^=]*=([^&\s]+)", "[FILTERED_CVV]"),
        # Personal Information
        (r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b", "[FILTERED_SSN]"),
        (r"ssn[^=]*=([^&\s]+)", "[FILTERED_SSN]"),
        # Email patterns (optional - only if you want to hide emails)
        # (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[FILTERED_EMAIL]'),
    ]

    def filter(self, record):
        """Filter sensitive data from log message and arguments"""
        # Filter message string
        if isinstance(record.msg, str):
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                record.msg = re.sub(
                    pattern, replacement, record.msg, flags=re.IGNORECASE
                )

        # Filter dictionary arguments
        if isinstance(record.args, dict):
            record.args = self._filter_dict(record.args)

        # Filter extra data if present
        if hasattr(record, "data") and isinstance(record.data, dict):
            record.data = self._filter_dict(record.data)

        return True

    def _filter_dict(self, data):
        """Recursively filter sensitive keys in dictionaries"""
        sensitive_keys = [
            "password",
            "passwd",
            "pwd",
            "token",
            "access_token",
            "refresh_token",
            "secret",
            "api_key",
            "apikey",
            "credit_card",
            "cc_number",
            "cvv",
            "ssn",
            "social_security",
            "private_key",
            "authorization",
        ]

        filtered = {}
        for key, value in data.items():
            if any(sensitive in str(key).lower() for sensitive in sensitive_keys):
                filtered[key] = "[FILTERED]"
            elif isinstance(value, dict):
                filtered[key] = self._filter_dict(value)
            elif isinstance(value, list):
                filtered[key] = [
                    self._filter_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                filtered[key] = value

        return filtered


class ModuleFilter(logging.Filter):
    """Filter logs by module name"""

    def __init__(self, module_name=None, name=""):
        super().__init__(name)
        self.module_name = module_name

    def filter(self, record):
        if self.module_name:
            return record.module == self.module_name
        return True


class SlowQueryFilter(logging.Filter):
    """Filter to only log slow database queries"""

    def __init__(self, threshold_ms=100, name=""):
        super().__init__(name)
        self.threshold_ms = threshold_ms

    def filter(self, record):
        """Only pass records for queries slower than threshold"""
        if hasattr(record, "duration"):
            return record.duration * 1000 >= self.threshold_ms
        return True


class DatabaseLogHandler(logging.Handler):
    """
    Handler to save logs in database.
    Uses lazy imports to avoid circular dependencies.
    """

    def emit(self, record):
        try:
            # Lazy import to avoid circular dependency during Django initialization
            SystemLog = apps.get_model("core", "SystemLog")

            with transaction.atomic():
                log_entry = SystemLog(
                    level=record.levelname,
                    logger=record.name,
                    message=self.format(record),
                    module=record.module,
                    function=record.funcName,
                    line=record.lineno,
                    path=record.pathname,
                    exception=self._format_exception(record) if record.exc_info else "",
                )

                # Extract request information if available
                if hasattr(record, "request"):
                    request = getattr(record, "request")
                    log_entry.user = (
                        request.user
                        if hasattr(request.user, "is_authenticated")
                        and request.user.is_authenticated
                        else None
                    )
                    log_entry.ip_address = self._get_client_ip(request)
                    log_entry.request_method = request.method
                    log_entry.request_path = request.path

                log_entry.save()

        except Exception:
            # Don't let logging errors break the application
            self.handleError(record)

    def _get_client_ip(self, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    def _format_exception(self, record):
        """Format exception traceback"""
        if record.exc_info:
            formatter = self.formatter or logging.Formatter()
            return formatter.formatException(record.exc_info)
        return ""


class EmailWithContextHandler(logging.Handler):
    """
    Enhanced email handler that includes request context and environment info.
    Useful for production error alerts.
    """

    def emit(self, record):
        try:
            from django.core.mail import mail_admins
            from django.conf import settings

            environment = getattr(settings, "ENVIRONMENT", "development")
            subject = f"[{environment}] {record.levelname}: {record.getMessage()[:100]}"

            formatter = self.formatter or logging.Formatter()
            message = self._build_message(record, formatter)

            mail_admins(subject, message, fail_silently=True)

        except Exception:
            self.handleError(record)

    def _build_message(self, record, formatter):
        """Build detailed error message"""
        message = f"""
Error Details:
==============
Message: {record.getMessage()}
Logger: {record.name}
Module: {record.module}
Function: {record.funcName}
Line: {record.lineno}
Time: {formatter.formatTime(record)}
Thread: {record.thread}
Process: {record.process}
"""

        # Add exception info
        if record.exc_info:
            message += f"\n\nTraceback:\n{formatter.formatException(record.exc_info)}"

        # Add request info if available
        if hasattr(record, "request"):
            request = getattr(record, "request")
            message += f"""

Request Information:
===================
Method: {request.method}
Path: {request.path}
Full Path: {request.get_full_path()}
User: {request.user}
IP Address: {self._get_client_ip(request)}
User Agent: {request.META.get('HTTP_USER_AGENT', 'N/A')}
"""

            # Add POST data (filtered)
            if request.POST:
                message += f"\nPOST Data: {self._filter_sensitive(dict(request.POST))}"

        # Add extra data if available
        if hasattr(record, "data"):
            message += f"\n\nExtra Data:\n{record.data}"

        return message

    def _get_client_ip(self, request):
        """Extract client IP"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    def _filter_sensitive(self, data):
        """Quick filter of sensitive data for email"""
        sensitive_keys = ["password", "token", "secret", "api_key"]
        filtered = {}
        for key, value in data.items():
            if any(s in key.lower() for s in sensitive_keys):
                filtered[key] = "[FILTERED]"
            else:
                filtered[key] = value
        return filtered
