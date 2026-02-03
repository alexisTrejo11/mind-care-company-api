from django.forms import ValidationError
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.core.exceptions.base_exceptions import ValidationError
from apps.core.decorators.error_handler import api_error_handler
from apps.core.decorators.rate_limit import rate_limit
from apps.core.responses.api_response import APIResponse

from ..services.user_service import UserService
from ..serializers import (
    UserLoginSerializer,
    UserProfileSerializer,
)


class UserLoginView(APIView):
    """
    POST api/auth/login/
    Authenticate user and return JWT tokens
    """

    permission_classes = [AllowAny]
    serializer_class = UserLoginSerializer

    @api_error_handler
    @rate_limit(profile="SENSITIVE", scope="login")
    def post(self, request):
        """Authenticate user and return JWT tokens"""
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        user, tokens = UserService.authenticate_user(email, password)

        return APIResponse.success(
            message="Login successful",
            data={
                "user": UserProfileSerializer(user).data,
                "tokens": tokens,
            },
        )


class UserLogoutView(APIView):
    """
    POST api/auth/logout/
    Logout user and blacklist refresh token
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @rate_limit(profile="STANDARD", scope="logout")
    def post(self, request):
        """Logout user and blacklist refresh token"""
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh_token = request.data.get("refresh_token")

        if not refresh_token:
            raise ValidationError(detail="Refresh token is required")

        token = RefreshToken(refresh_token)
        token.blacklist()

        return APIResponse.success(message="Logout successful")


class RefreshTokenView(APIView):
    """
    POST api/auth/token/refresh/
    Refresh JWT access token using refresh token
    """

    permission_classes = [AllowAny]

    @api_error_handler
    @rate_limit(profile="SENSITIVE", scope="token_refresh")
    def post(self, request):
        """Refresh JWT access token using refresh token"""
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError

        refresh_token = request.data.get("refresh_token")

        if not refresh_token:
            raise ValidationError(detail="Refresh token is required")

        try:
            token = RefreshToken(refresh_token)
            new_access_token = str(token.access_token)
        except TokenError:
            raise ValidationError(detail="Invalid refresh token")

        return APIResponse.success(
            message="Token refreshed successfully",
            data={"access_token": new_access_token},
        )
