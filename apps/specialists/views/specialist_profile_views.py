from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from core.decorators.error_handler import api_error_handler
from core.decorators.permissions import require_permissions, user_is_specialist
from core.responses.api_response import APIResponse
from core.exceptions.base_exceptions import NotFoundError
from ..serializers import SpecialistSerializer, SpecialistDetailSerializer
from ..services import SpecialistServiceLayer


class MySpecialistProfileView(APIView):
    """
    GET /api/specialists/me/
    Obtener perfil del especialista actual
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_specialist])
    def get(self, request):
        """Obtener perfil del especialista actual"""
        if not hasattr(request.user, "specialist_profile"):
            raise NotFoundError(detail="User is not a specialist")

        result = SpecialistServiceLayer.get_specialist_detail(
            request.user.specialist_profile.id
        )

        specialist_data = SpecialistDetailSerializer(result["specialist"]).data
        specialist_data["stats"] = result["stats"]

        return APIResponse.success(
            message="Specialist profile retrieved", data=specialist_data
        )

    @api_error_handler
    @require_permissions([user_is_specialist])
    def patch(self, request):
        """Actualizar perfil propio"""
        if not hasattr(request.user, "specialist_profile"):
            raise NotFoundError(detail="User is not a specialist")

        serializer = SpecialistSerializer(
            request.user.specialist_profile, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)

        specialist = SpecialistServiceLayer.update_specialist(
            request.user.specialist_profile.id, **serializer.validated_data
        )

        return APIResponse.success(
            message="Profile updated successfully",
            data=SpecialistSerializer(specialist).data,
        )
