from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from apps.users.serializers import EmailActivationSerializer
from apps.core.decorators.error_handler import api_error_handler
from apps.core.responses.api_response import APIResponse
from ..services.user_service import UserService


class EmailActivationView(APIView):
    """
    POST api/auth/activate/
    Activate user account via email token
    """

    permission_classes = [AllowAny]
    serializer_class = EmailActivationSerializer

    @api_error_handler
    @rate_limit(profile="RESTRICTED", scope="email_activation")
    def post(self, request):
        """Activar usuario"""
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]

        user = UserService.activate_user(token)

        return APIResponse.success(
            message="Account activated successfully! You can now log in.",
            data={"email": user.email},
        )
