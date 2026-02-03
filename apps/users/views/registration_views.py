from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from apps.core.decorators.error_handler import api_error_handler
from apps.core.decorators.rate_limit import rate_limit
from apps.core.responses.api_response import APIResponse
from ..services.user_service import UserService
from ..serializers import UserRegistrationSerializer

from ..tasks import send_welcome_email


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

        # Async Task
        send_welcome_email.delay(
            user_id=str(user.pk),
            user_email=user.email,
            user_name=user.get_full_name(),
            activation_token=tokens["activation_token"],
        )

        return APIResponse.created(
            message="Registration successful! Please check your email to activate your account.",
            data={
                "email": user.email,
                "user_id": user.pk,
                "user_type": user.user_type,
            },
        )
