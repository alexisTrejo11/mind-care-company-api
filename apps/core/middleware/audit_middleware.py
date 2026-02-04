import logging
import json
import time
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

audit_logger = logging.getLogger("audit")


class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log all HTTP requests and responses for audit purposes.
    Captures user actions, IP addresses, and response status codes.
    """

    EXCLUDED_PATHS = [
        "/static/",
        "/media/",
        "/health/",
        "/metrics/",
        "/__debug__/",
        "api/v2/schema/",
        "/admin/",
    ]

    MUTATION_METHODS = ["POST", "PUT", "PATCH", "DELETE"]

    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request):
        """Capture request start time"""
        request._audit_start_time = time.time()
        return None

    def process_response(self, request, response):
        """Log the request/response for audit purposes"""

        # Skip excluded paths
        if any(request.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return response

        # Skip GET requests on read-only endpoints
        """
        if request.method == "GET" and not self._is_sensitive_endpoint(request.path):
            return response
        """

        # Calculate request duration
        duration = time.time() - getattr(request, "_audit_start_time", time.time())

        # Build audit log data
        audit_data = {
            "timestamp": time.time(),
            "user_id": str(request.user.id) if request.user.is_authenticated else None,
            "username": (
                str(request.user.username)
                if request.user.is_authenticated
                else "Anonymous"
            ),
            "ip_address": self._get_client_ip(request),
            "method": request.method,
            "path": request.path,
            "full_path": request.get_full_path(),
            "status_code": response.status_code,
            "duration": round(duration, 4),
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            "referer": request.META.get("HTTP_REFERER", ""),
        }

        # Add request body for mutation operations (be careful with sensitive data)
        if request.method in self.MUTATION_METHODS:
            audit_data["request_body"] = self._get_safe_request_body(request)

        # Add query parameters for GET requests
        if request.method == "GET" and request.GET:
            audit_data["query_params"] = dict(request.GET)

        # Log based on status code
        log_level = self._get_log_level(response.status_code)
        action = self._determine_action(request)

        audit_logger.log(
            log_level,
            f"{action} - {request.method} {request.path} - Status: {response.status_code}",
            extra={"audit_data": audit_data},
        )

        return response

    def _get_client_ip(self, request):
        """Extract the real client IP address"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # Take the first IP in the chain
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "")
        return ip

    def _get_safe_request_body(self, request):
        """
        Get request body, but filter sensitive data.
        Only works for JSON and form data.
        """
        try:
            if request.content_type == "application/json":
                body = json.loads(request.body.decode("utf-8"))
                return self._filter_sensitive_data(body)
            elif request.POST:
                body = dict(request.POST)
                return self._filter_sensitive_data(body)
        except Exception:
            pass
        return None

    def _filter_sensitive_data(self, data):
        """Remove sensitive fields from data"""
        if not isinstance(data, dict):
            return data

        sensitive_fields = [
            "password",
            "password_confirmation",
            "old_password",
            "new_password",
            "token",
            "access_token",
            "refresh_token",
            "api_key",
            "secret",
            "credit_card",
            "cc_number",
            "cvv",
            "ssn",
            "social_security",
        ]

        filtered = data.copy()
        for key in list(filtered.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_fields):
                filtered[key] = "[FILTERED]"
        return filtered

    def _get_log_level(self, status_code):
        """Determine log level based on status code"""
        if status_code >= 500:
            return logging.ERROR
        elif status_code >= 400:
            return logging.WARNING
        else:
            return logging.INFO

    def _determine_action(self, request):
        """Determine the action type from the request"""
        method_actions = {
            "POST": "CREATE",
            "PUT": "UPDATE",
            "PATCH": "UPDATE",
            "DELETE": "DELETE",
            "GET": "READ",
        }
        return method_actions.get(request.method, "ACTION")

    def _is_sensitive_endpoint(self, path):
        """
        Check if the endpoint is sensitive and should always be logged.
        Add your sensitive endpoints here.
        """
        sensitive_patterns = [
            "/admin/",
            "/api/auth/",
            "/api/users/",
            "/api/payments/",
            "/api/settings/",
        ]
        return any(pattern in path for pattern in sensitive_patterns)
