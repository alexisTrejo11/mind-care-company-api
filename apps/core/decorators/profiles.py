"""
Rate Limit Profiles Configuration

This module defines predefined rate limit profiles for different types of API endpoints.
Each profile specifies rate limits optimized for different security and usage scenarios.

Profile Types:
- SENSITIVE: Critical authentication and security endpoints (login, password reset)
- RESTRICTED: Resource-intensive or sensitive operations (account creation, data modifications)
- STANDARD: Regular authenticated API operations
- PUBLIC: Public read-only endpoints
- ELEVATED: Higher limits for trusted operations
- ADMIN: Administrative operations with moderate limits
"""

from typing import Dict, Tuple


class RateLimitProfiles:
    """
    Predefined rate limit profiles for API endpoints.

    Each profile is a tuple of (key_type, rate, scope_suffix) where:
    - key_type: What to track ('ip', 'user_id', or 'email')
    - rate: Rate string (e.g., '5/min', '100/day')
    - scope_suffix: Optional suffix for the scope (defaults to action name)
    """

    # ========== AUTHENTICATION & SECURITY ==========
    SENSITIVE = {
        "key_type": "email",
        "rate": "5/1min",  # Very restrictive for auth attempts
        "fallback_key": "ip",
        "description": "For login, password reset requests, and other auth operations",
    }

    # ========== ACCOUNT MANAGEMENT ==========
    RESTRICTED = {
        "key_type": "ip",
        "rate": "3/1hour",  # Prevent account creation abuse
        "fallback_key": "ip",
        "description": "For registration, account activation, and critical modifications",
    }

    # ========== STANDARD OPERATIONS ==========
    STANDARD = {
        "key_type": "user_id",
        "rate": "60/1min",  # Standard rate for authenticated users
        "fallback_key": "ip",
        "description": "For regular authenticated API operations",
    }

    # ========== PUBLIC ENDPOINTS ==========
    PUBLIC = {
        "key_type": "ip",
        "rate": "30/1min",  # Moderate rate for public access
        "fallback_key": "ip",
        "description": "For public read-only endpoints",
    }

    # ========== ELEVATED ACCESS ==========
    ELEVATED = {
        "key_type": "user_id",
        "rate": "100/1min",  # Higher limits for power users
        "fallback_key": "ip",
        "description": "For trusted operations and power users",
    }

    # ========== ADMINISTRATIVE ==========
    ADMIN = {
        "key_type": "user_id",
        "rate": "200/1min",  # High limits for admin operations
        "fallback_key": "ip",
        "description": "For administrative operations",
    }

    # ========== WRITE OPERATIONS ==========
    WRITE_OPERATION = {
        "key_type": "user_id",
        "rate": "30/1min",  # Moderate rate for creates/updates
        "fallback_key": "ip",
        "description": "For create, update, and delete operations",
    }

    # ========== READ OPERATIONS ==========
    READ_OPERATION = {
        "key_type": "user_id",
        "rate": "100/1min",  # Higher rate for read operations
        "fallback_key": "ip",
        "description": "For list and detail operations",
    }

    # ========== FINANCIAL TRANSACTIONS ==========
    PAYMENT = {
        "key_type": "user_id",
        "rate": "10/1min",  # Restrictive for payment operations
        "fallback_key": "ip",
        "description": "For payment processing and financial transactions",
    }

    # ========== BULK OPERATIONS ==========
    BULK = {
        "key_type": "user_id",
        "rate": "5/1min",  # Very restrictive for bulk operations
        "fallback_key": "ip",
        "description": "For bulk export, import, or batch operations",
    }

    @classmethod
    def get_profile(cls, profile_name: str) -> Dict[str, str]:
        """
        Get a rate limit profile by name.

        Args:
            profile_name: Name of the profile (e.g., 'SENSITIVE', 'STANDARD')

        Returns:
            Dictionary with rate limit configuration

        Raises:
            ValueError: If profile name doesn't exist
        """
        profile = getattr(cls, profile_name.upper(), None)
        if profile is None:
            raise ValueError(
                f"Rate limit profile '{profile_name}' not found. "
                f"Available profiles: {cls.get_available_profiles()}"
            )
        return profile

    @classmethod
    def get_available_profiles(cls) -> list:
        """Get list of all available profile names."""
        return [
            attr
            for attr in dir(cls)
            if not attr.startswith("_")
            and attr.isupper()
            and not callable(getattr(cls, attr))
        ]


# Convenience constants for easy import
SENSITIVE = RateLimitProfiles.SENSITIVE
RESTRICTED = RateLimitProfiles.RESTRICTED
STANDARD = RateLimitProfiles.STANDARD
PUBLIC = RateLimitProfiles.PUBLIC
ELEVATED = RateLimitProfiles.ELEVATED
ADMIN = RateLimitProfiles.ADMIN
WRITE_OPERATION = RateLimitProfiles.WRITE_OPERATION
READ_OPERATION = RateLimitProfiles.READ_OPERATION
PAYMENT = RateLimitProfiles.PAYMENT
BULK = RateLimitProfiles.BULK
