"""
Development settings - uses SQLite for local development
"""

from .base import *

# Development mode
DEBUG = True

# Database - SQLite for development
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Disable cache in development (optional)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Email backend for development (console)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Django Debug Toolbar (optional)
if DEBUG:
    INSTALLED_APPS += [
        # "debug_toolbar",
    ]
    MIDDLEWARE += [
        # "debug_toolbar.middleware.DebugToolbarMiddleware",
    ]
    INTERNAL_IPS = [
        "127.0.0.1",
        "localhost",
    ]

# Disable some security settings for development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Logging - more verbose in development
# LOGGING["loggers"]["django"]["level"] = "DEBUG"
