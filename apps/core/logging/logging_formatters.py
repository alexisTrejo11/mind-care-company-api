import json
import logging
from datetime import datetime
from django.utils.timezone import now
import traceback


class JSONFormatter(logging.Formatter):
    """Log formatter to JSON"""

    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
            "path": record.pathname,
            "process": record.process,
            "thread": record.thread,
        }

        # Add exception if exists
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra data if exists
        if hasattr(record, "extra_data"):
            log_data["extra"] = getattr(record, "extra_data", None)

        # Add request info if exists
        if hasattr(record, "request"):
            request = getattr(record, "request")
            log_data["request"] = {
                "method": request.method,
                "path": request.path,
                "user": (
                    str(request.user) if request.user.is_authenticated else "anonymous"
                ),
                "ip": self.get_client_ip(request),
            }

        return json.dumps(log_data, ensure_ascii=False)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return request.META.get("REMOTE_ADDR", "unknown")


class RequestFormatter(logging.Formatter):
    """Formateador específico para logs de requests"""

    def format(self, record):
        if hasattr(record, "request"):
            request = getattr(record, "request")
            record.msg = f"{request.method} {request.path} - {record.msg}"
        return super().format(record)
