from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from apps.core.decorators.error_handler import api_error_handler
from apps.core.decorators.rate_limit import rate_limit
from apps.core.responses.api_response import APIResponse
from apps.core.shared import mask_email
from ..services.user_service import UserService
from ..serializers import (
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    PasswordChangeSerializer,
)
from ..tasks import (
    send_password_reset_email,
    send_password_changed_notification,
)


class PasswordResetRequestView(APIView):
    """
    POST api/auth/password-reset/
    Request password reset email
    """

    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer

    @api_error_handler
    @rate_limit(profile="SENSITIVE", scope="password_reset")
    def post(self, request):
        """Solicitar reseteo de contraseña"""
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        # Llamar al servicio
        reset_token = UserService.request_password_reset(email)

        # Solo enviar email si hay token (usuario existe)
        if reset_token:
            send_password_reset_email.delay(
                user_email=email,
                reset_token=reset_token,
            )

        return APIResponse.success(
            message=f"If an account exists with {mask_email(email)}, "
            f"a password reset link has been sent."
        )


class PasswordResetConfirmView(APIView):
    """
    POST api/auth/password-reset/confirm/
    Confirm password reset with token
    """

    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    @api_error_handler
    @rate_limit(profile="RESTRICTED", scope="password_reset_confirm")
    def post(self, request):
        """Confirmar reseteo de contraseña"""
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["password"]

        # Llamar al servicio
        user = UserService.reset_password(token, new_password)

        # Enviar notificación
        send_password_changed_notification.delay(
            user_email=user.email,
            user_name=user.get_full_name(),
        )

        return APIResponse.success(
            message="Password has been reset successfully. "
            "You can now log in with your new password."
        )


class PasswordChangeView(APIView):
    """
    POST api/auth/password-change/
    Change password for authenticated user
    """

    permission_classes = [IsAuthenticated]
    serializer_class = PasswordChangeSerializer

    @api_error_handler
    @rate_limit(profile="STANDARD", scope="password_change")
    def post(self, request):
        """Cambiar contraseña"""
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        current_password = serializer.validated_data["current_password"]
        new_password = serializer.validated_data["new_password"]

        UserService.change_password(request.user, current_password, new_password)

        send_password_changed_notification.delay(
            user_email=request.user.email,
            user_name=request.user.get_full_name(),
        )

        return APIResponse.success(
            message="Password changed successfully. "
            "Please log in again with your new password."
        )
