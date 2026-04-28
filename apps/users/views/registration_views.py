from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from apps.core.decorators.error_handler import api_error_handler
from apps.core.decorators.rate_limit import rate_limit
from apps.core.responses.api_response import APIResponse
from ..services.user_service import UserService
from ..serializers import UserRegistrationSerializer
from apps.notification.tasks import send_notification
from apps.users.models import User
from apps.core.shared import generate_activation_token
import logging

logger = logging.getLogger(__name__)


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

        UserService.validate_user_register(**serializer.validated_data)

        logger.info(
            f"Registering new user with email: {serializer.validated_data.get('email')}"
        )
        user = User.objects.create_user(
            **serializer.validated_data,
        )

        logger.info(
            f"User registered successfully with email: {user.email}, sending activation email."
        )
        self._send_activation_account_email(user)

        logger.info(
            f"Registration process completed for user {user.email}. Activation email sent."
        )
        return APIResponse.created(
            message="Registration successful! Please check your email to activate your account.",
            data={
                "email": user.email,
                "user_id": user.pk,
                "user_type": user.user_type,
            },
        )

    def _send_activation_account_email(self, user):
        """Send activation email to the newly registered user."""
        activation_token = generate_activation_token(user)

        try:
            task_result = send_notification.delay(
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

            logger.info(
                f"Activation email task queued for user {user.email} with task ID: {task_result.id}"
            )
        except Exception as e:
            logger.error(
                f"Failed to queue activation email for user {user.email}: {str(e)}"
            )
