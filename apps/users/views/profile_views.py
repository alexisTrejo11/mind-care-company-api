from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from core.decorators.error_handler import api_error_handler
from core.responses.api_response import APIResponse
from ..services.user_service import UserService
from ..serializers import UserProfileSerializer


class UserProfileView(APIView):
    """
    GET/PUT/PATCH api/auth/profile/
    Get or update user profile
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def get(self, request):
        """Obtener perfil"""
        serializer = UserProfileSerializer(request.user)
        return APIResponse.success(data=serializer.data)

    @api_error_handler
    def put(self, request):
        """Actualizar perfil completo"""
        return self._update_profile(request, partial=False)

    @api_error_handler
    def patch(self, request):
        """Actualizar perfil parcial"""
        return self._update_profile(request, partial=True)

    def _update_profile(self, request, partial=False):
        """Lógica compartida para actualizar perfil"""
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)

        user = UserService.update_profile(request.user, serializer.validated_data)

        return APIResponse.success(
            message="Profile updated successfully",
            data=UserProfileSerializer(user).data,
        )
