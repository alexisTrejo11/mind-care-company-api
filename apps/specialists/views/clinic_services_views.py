from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.generics import ListAPIView, RetrieveAPIView
from django.db.models import Q

from core.decorators.error_handler import api_error_handler
from core.decorators.permissions import (
    require_permissions,
    user_is_specialist,
    user_is_admin,
)
from core.responses.api_response import APIResponse
from core.exceptions.base_exceptions import NotFoundError
from rest_framework.exceptions import ValidationError

from ..models import Specialist, Service, Availability
from ..serializers import (
    SpecialistSerializer,
    SpecialistDetailSerializer,
    SpecialistServiceSerializer,
    AvailabilitySerializer,
    ServiceSerializer,
)
from ..services import (
    SpecialistServiceLayer,
    AvailabilityService,
    ServiceService,
)


class SpecialistServicesView(APIView):
    """
    GET/POST /api/specialists/<id>/services/
    Gestionar servicios de especialista
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def get(self, request, specialist_id):
        """Listar servicios del especialista"""
        specialist = Specialist.objects.get(id=specialist_id)
        services = specialist.services.select_related("service").all()

        serializer = SpecialistServiceSerializer(services, many=True)

        return APIResponse.success(
            message="Specialist services retrieved", data=serializer.data
        )

    @api_error_handler
    @require_permissions([user_is_admin, user_is_specialist])
    def post(self, request, specialist_id):
        """Agregar servicio a especialista"""
        serializer = SpecialistServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Verificar permisos
        if request.user.user_type == "specialist":
            if request.user.specialist_profile.id != specialist_id:
                raise PermissionError("Cannot add services to another specialist")

        # Usar servicio para agregar
        specialist_service = SpecialistServiceLayer.add_service_to_specialist(
            specialist_id=specialist_id,
            service_id=serializer.validated_data["service"].id,
            price_override=serializer.validated_data.get("price_override"),
        )

        return APIResponse.created(
            message="Service added to specialist",
            data=SpecialistServiceSerializer(specialist_service).data,
        )
    
class ServiceListView(APIView):
    """
    GET /api/services/
    Listar servicios disponibles
    """

    permission_classes = [AllowAny]

    @api_error_handler
    def get(self, request):
        """Listar servicios"""
        category = request.query_params.get("category")
        active_only = request.query_params.get("active_only", "true").lower() == "true"

        # Usar servicio para obtener servicios
        services = ServiceService.get_services_by_category(category, active_only)

        serializer = ServiceSerializer(services, many=True)

        return APIResponse.success(message="Services retrieved", data=serializer.data)


class ServiceCreateView(APIView):
    """
    POST /api/services/create/
    Crear nuevo servicio (admin only)
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_admin])
    def post(self, request):
        """Crear servicio"""
        serializer = ServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Usar servicio para crear
        service = ServiceService.create_service(**serializer.validated_data)

        return APIResponse.created(
            message="Service created successfully", data=ServiceSerializer(service).data
        )
