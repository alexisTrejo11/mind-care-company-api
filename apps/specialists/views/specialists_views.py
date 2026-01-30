from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny

from core.decorators.error_handler import api_error_handler
from core.decorators.permissions import (
    require_permissions,
    user_is_specialist,
    user_is_admin,
)
from core.responses.api_response import APIResponse
from ..serializers import (
    SpecialistSerializer,
    SpecialistDetailSerializer,
    SpecialistCreateSerializer,
    SpecialistSearchSerializer,
)
from ..services import SpecialistServiceLayer



class SpecialistListView(APIView):
    """
    GET /api/specialists/
    Listar y buscar especialistas
    """

    permission_classes = [AllowAny]

    @api_error_handler
    def get(self, request):
        """Buscar y listar especialistas"""
        # Validar parámetros de búsqueda
        search_serializer = SpecialistSearchSerializer(data=request.query_params)
        search_serializer.is_valid(raise_exception=True)

        filters = search_serializer.validated_data
        page = filters.pop("page", 1)
        page_size = filters.pop("page_size", 20)

        # Usar servicio para búsqueda
        specialists, pagination = SpecialistServiceLayer.search_specialists(
            filters, page, page_size
        )

        serializer = SpecialistSerializer(specialists, many=True)

        return APIResponse.success(
            message="Specialists retrieved successfully",
            data=serializer.data,
            pagination=pagination,
        )


class SpecialistDetailView(APIView):
    """
    GET /api/specialists/<id>/
    Obtener detalles de especialista
    """

    permission_classes = [AllowAny]

    @api_error_handler
    def get(self, request, specialist_id):
        """Obtener detalles de especialista"""
        result = SpecialistServiceLayer.get_specialist_detail(specialist_id)

        specialist_data = SpecialistDetailSerializer(result["specialist"]).data
        specialist_data["stats"] = result["stats"]

        return APIResponse.success(
            message="Specialist details retrieved", data=specialist_data
        )



class SpecialistCreateView(APIView):
    """
    POST /api/specialists/create/
    Crear nuevo perfil de especialista
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_admin])
    def post(self, request):
        """Crear especialista"""
        serializer = SpecialistCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Usar servicio para crear
        specialist = SpecialistServiceLayer.create_specialist(
            **serializer.validated_data
        )

        return APIResponse.created(
            message="Specialist profile created successfully",
            data=SpecialistSerializer(specialist).data,
        )
    

class SpecialistUpdateView(APIView):
    """
    PATCH /api/specialists/<id>/update/
    Actualizar perfil de especialista
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_admin, user_is_specialist])
    def patch(self, request, specialist_id):
        """Actualizar especialista"""
        # Para especialistas, solo pueden actualizar su propio perfil
        if request.user.user_type == "specialist":
            if not hasattr(request.user, "specialist_profile"):
                raise PermissionError("User is not a specialist")
            if request.user.specialist_profile.id != specialist_id:
                raise PermissionError("Cannot update another specialist's profile")

        serializer = SpecialistSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Usar servicio para actualizar
        specialist = SpecialistServiceLayer.update_specialist(
            specialist_id, **serializer.validated_data
        )

        return APIResponse.success(
            message="Specialist profile updated",
            data=SpecialistSerializer(specialist).data,
        )
