from django.forms import ValidationError
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated

from core.exceptions.base_exceptions import ValidationError
from core.decorators.error_handler import api_error_handler, rate_limit
from core.responses.api_response import APIResponse

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
    @rate_limit(key="email", rate="5/15min", scope="login")
    def post(self, request):
        """Autenticar usuario"""
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        # Llamar al servicio
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
    def post(self, request):
        """Cerrar sesión"""
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh_token = request.data.get("refresh_token")

        if not refresh_token:
            raise ValidationError(detail="Refresh token is required")

        token = RefreshToken(refresh_token)
        token.blacklist()

        return APIResponse.success(message="Logout successful")
