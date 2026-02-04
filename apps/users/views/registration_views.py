from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from apps.core.decorators.error_handler import api_error_handler
from apps.core.decorators.rate_limit import rate_limit
from apps.core.responses.api_response import APIResponse
from ..services.user_service import UserService
from ..serializers import UserRegistrationSerializer
from apps.notification.tasks import send_notification


class UserRegistrationView(APIView):
    """
    POST api/auth/register/
    Register a new user account
    """

    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer

    @api_error_handler
    @rate_limit(profile="RESTRICTED", scope="registration")
    def post(self, request):
        """Register a new user account. Will send activation email."""
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, tokens = UserService.register_user(**serializer.validated_data)

        self._send_activation_email(user, tokens["activation_token"])

        return APIResponse.created(
            message="Registration successful! Please check your email to activate your account.",
            data={
                "email": user.email,
                "user_id": user.pk,
                "user_type": user.user_type,
            },
        )

    def _send_activation_email(self, user, activation_token):
        """Send activation email to the newly registered user."""
        send_notification.delay(
            template_name="auth_notification",
            user_id=str(user.pk),
            context={
                "user_name": user.get_full_name(),
                "activation_token": activation_token,
                "email": user.email,
            },
            category="auth",
            priority="high",
            immediate=True,
        )
