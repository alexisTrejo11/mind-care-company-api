from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from core.decorators.error_handler import api_error_handler
from core.decorators.rate_limit import rate_limit
from core.responses.api_response import APIResponse
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
    @rate_limit(key_type="ip", rate="5/hour", scope="registration")
    def post(self, request):
        """Registrar nuevo usuario"""
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Extraer datos validados
        data = serializer.validated_data

        # Llamar al servicio de negocio
        user, tokens = UserService.register_user(
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone=data.get("phone"),
            user_type=data.get("user_type", "patient"),
            date_of_birth=data.get("date_of_birth"),
        )

        # Enviar email de bienvenida (asíncrono)
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
