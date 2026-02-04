from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer


@extend_schema_serializer(component_name="EmailActivation")
class EmailActivationSerializer(serializers.Serializer):
    """
    Serializer for email activation token validation.

    Validates email confirmation token for account activation
    or email address verification processes.

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | token | String | Yes | JWT string | Email activation token |

    **Field Specifications:**

    1. **token field**:
       - JWT token from activation email
       - Contains user ID and email verification data
       - Validated for format, signature, and expiration
       - Single-use token

    **Token Characteristics:**
    - JWT format with user identification
    - Contains email verification intent
    - Short expiration (typically 24 hours)
    - One-time use design
    - Cryptographic signature verification

    **Activation Process:**
    1. Token format validation
    2. Signature verification
    3. Expiration check
    4. Single-use validation
    5. User account activation

    **Error Conditions:**
    - Invalid token format
    - Expired token
    - Already used token
    - Signature mismatch
    """

    token = serializers.CharField(
        required=True, help_text="Email activation token received via email"
    )


@extend_schema_serializer(component_name="TokenRefresh")
class TokenRefreshSerializer(serializers.Serializer):
    """
    Serializer for JWT token refresh operation.

    Accepts refresh token and returns new access token
    for extending authenticated session without re-login.

    **Data Schema:**

    | Field | Type | Required | Format | Description |
    |-------|------|----------|--------|-------------|
    | refresh | String | Yes | JWT string | Valid refresh token |

    **Field Specifications:**

    1. **refresh field**:
       - Valid JWT refresh token
       - Not expired refresh token
       - Properly signed token
       - Returns new access token in validated data

    **Token Flow:**
    - Input: Valid refresh token
    - Output: New access token (added to attrs dict)
    - Refresh token remains valid for rotation

    **Security Characteristics:**
    - Refresh tokens have longer expiration
    - Access tokens have shorter expiration
    - Token rotation capability
    - Blacklist support for revoked tokens

    **Usage Pattern:**
    1. Client receives access + refresh tokens on login
    2. Access token expires (short-lived)
    3. Client sends refresh token to get new access token
    4. Process repeats until refresh token expires

    **Output Data:**
    After validation, serializer adds 'access' key to attrs
    containing new JWT access token string.
    """

    refresh = serializers.CharField(
        required=True,
        help_text="Valid JWT refresh token for obtaining new access token",
    )
