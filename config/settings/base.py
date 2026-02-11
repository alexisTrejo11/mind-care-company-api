"""
Base Django settings for config project.
Common settings shared across all environments.
"""

from pathlib import Path
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Initialize environ
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)

# Read .env file
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-this-in-production")

DEBUG = env("DEBUG")

ALLOWED_HOSTS = env("ALLOWED_HOSTS")


# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party apps
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    # Local apps
    "apps.users",
    "apps.specialists",
    "apps.appointments",
    "apps.medical",
    "apps.billing",
    "apps.notification",
    "apps.core",
]

AUTH_USER_MODEL = "users.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.audit_middleware.AuditLoggingMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Internationalization
LANGUAGE_CODE = env("LANGUAGE_CODE", default="en-us")
TIME_ZONE = env("TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = env("STATIC_URL", default="/static/")
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = []

# Media files
MEDIA_URL = env("MEDIA_URL", default="/media/")
MEDIA_ROOT = BASE_DIR / "media"


# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "apps.core.exceptions.handlers.custom_exception_handler",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.CustomPageNumberPagination",
    "PAGE_SIZE": env.int("PAGE_SIZE", default=20),
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS", default=["http://localhost:3000", "http://127.0.0.1:3000"]
)

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS", default=["http://localhost:8000", "http://127.0.0.1:8000"]
)


# Redis Cache Configuration
REDIS_HOST = env("REDIS_HOST", default="localhost")
REDIS_PORT = env("REDIS_PORT", default="6379")
REDIS_URL = env("REDIS_URL", default=f"redis://{REDIS_HOST}:{REDIS_PORT}/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SERIALIZER": "django_redis.serializers.pickle.PickleSerializer",
        },
        "KEY_PREFIX": env("CACHE_KEY_PREFIX", default="mind_care_hub"),
        "TIMEOUT": env.int("CACHE_TIMEOUT", default=900),  # 15 minutes
    }
}


# Logging Configuration
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    # ====================
    # FORMATTERS
    # ====================
    "formatters": {
        "verbose": {
            "format": "[{asctime}] [{levelname}] [{name}] [{process:d}] [{thread:d}] {module}.{funcName}:{lineno} - {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "[{asctime}] [{levelname}] [{name}] - {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "json": {
            "()": "apps.core.logging.logging_formatters.JSONFormatter",
        },
        "audit": {
            "format": "[{asctime}] [{levelname}] AUDIT - {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    # FILTERS
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
        "exclude_sensitive": {
            "()": "apps.core.logging.logging_filters.ExcludeSensitiveFilter",
        },
        # Filter slow queries only (>100ms)
        "slow_queries": {
            "()": "apps.core.logging.logging_filters.SlowQueryFilter",
            "threshold_ms": 100,
        },
    },
    # HANDLERS
    "handlers": {
        # Console output (development)
        "console": {
            "level": "DEBUG" if DEBUG else "INFO",
            "filters": ["require_debug_true", "exclude_sensitive"],
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        # General application logs
        "file_general": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "django.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 10,
            "formatter": "verbose",
            "encoding": "utf-8",
            "filters": ["exclude_sensitive"],
        },
        # Error logs only
        "file_errors": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "errors.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 10,
            "formatter": "verbose",
            "encoding": "utf-8",
            "filters": ["exclude_sensitive"],
        },
        # JSON formatted logs (for ELK/Logstash)
        "file_json": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "app.json.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 10,
            "formatter": "json",
            "encoding": "utf-8",
            "filters": ["exclude_sensitive"],
        },
        # Audit logs (time-based rotation, keep 90 days)
        "audit_file": {
            "level": "INFO",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": LOGS_DIR / "audit.log",
            "when": "midnight",
            "interval": 1,
            "backupCount": 90,  # Keep 90 days
            "formatter": "audit",
            "encoding": "utf-8",
            # Don't filter sensitive data from audit logs - they need full context
        },
        # Database handler (ERROR level only to avoid performance issues)
        "database": {
            "level": "ERROR",
            "class": "apps.core.logging.logging_filters.DatabaseLogHandler",
            "formatter": "verbose",
            "filters": ["exclude_sensitive"],
        },
        # Email admins for critical errors (production only)
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "apps.core.logging.logging_filters.EmailWithContextHandler",
        },
        # Celery logs
        "celery_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "celery.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 10,
            "formatter": "verbose",
            "encoding": "utf-8",
            "filters": ["exclude_sensitive"],
        },
        # Performance logs
        "performance_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "performance.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    # LOGGERS
    "loggers": {
        # Django framework
        "django": {
            "handlers": ["console", "file_general"],
            "level": "INFO",
            "propagate": False,
        },
        # Database queries (only in DEBUG mode or slow queries)
        "django.db.backends": {
            "handlers": ["console"] if DEBUG else [],
            "level": "DEBUG" if DEBUG else "WARNING",
            "propagate": False,
            "filters": [] if DEBUG else ["slow_queries"],
        },
        # HTTP requests (errors only)
        "django.request": {
            "handlers": ["file_errors", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
        # Security events
        "django.security": {
            "handlers": ["file_errors", "mail_admins", "audit_file"],
            "level": "WARNING",
            "propagate": False,
        },
        # Django server (development server)
        "django.server": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        # Your application
        "apps": {
            "handlers": ["console", "file_general", "file_json", "file_errors"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        # Audit logger (separate from application logs)
        "audit": {
            "handlers": ["audit_file", "database"],
            "level": "INFO",
            "propagate": False,
        },
        # Performance monitoring
        "performance": {
            "handlers": ["performance_file"],
            "level": "INFO",
            "propagate": False,
        },
        # Celery
        "celery": {
            "handlers": ["celery_file", "console"],
            "level": "INFO",
            "propagate": False,
        },
        "celery.task": {
            "handlers": ["celery_file"],
            "level": "INFO",
            "propagate": False,
        },
        # Third-party libraries (reduce noise)
        "requests": {
            "handlers": ["file_general"],
            "level": "WARNING",
            "propagate": False,
        },
        "urllib3": {
            "handlers": ["file_general"],
            "level": "WARNING",
            "propagate": False,
        },
        "boto3": {
            "handlers": ["file_general"],
            "level": "WARNING",
            "propagate": False,
        },
        "botocore": {
            "handlers": ["file_general"],
            "level": "WARNING",
            "propagate": False,
        },
        "elasticsearch": {
            "handlers": ["file_general"],
            "level": "WARNING",
            "propagate": False,
        },
        # Root logger (catches everything not specified above)
        "": {
            "handlers": ["console", "file_general", "file_errors"],
            "level": "INFO",
        },
    },
}


# Security Settings (Production will override these)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"


# JWT Settings
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=60)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}


# Email
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = False
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@mindcarehub.com")

# Get these from https://console.twilio.com/
TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID", default="your_account_sid_here")
TWILIO_AUTH_TOKEN = env(
    "TWILIO_AUTH_TOKEN", default="your_auth_token_here"
)  # Example: your_32_character_auth_token
TWILIO_PHONE_NUMBER = env("TWILIO_PHONE_NUMBER", default="+1234567890")


# Celery Configuration
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

# Celery Beat Schedule (for periodic tasks)
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "process-pending-notifications": {
        "task": "apps.notification.tasks.process_pending_notifications",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
}


SPECTACULAR_SETTINGS = {
    "TITLE": "Mind Care Hub API",
    "DESCRIPTION": "API documentation for Mind Care Hub",
    "VERSION": "2.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
