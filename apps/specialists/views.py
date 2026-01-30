# apps/specialists/views.py
"""
Views para gestión de especialistas y servicios
"""
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

from .models import Specialist, Service, Availability
from .serializers import (
    SpecialistSerializer,
    SpecialistDetailSerializer,
    SpecialistCreateSerializer,
    SpecialistServiceSerializer,
    AvailabilitySerializer,
    ServiceSerializer,
    SpecialistSearchSerializer,
)
from .services import (
    SpecialistServiceLayer,
    AvailabilityService,
    ServiceService,
)


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


class AvailabilityListView(APIView):
    """
    GET/POST /api/specialists/<id>/availability/
    Gestionar disponibilidad
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def get(self, request, specialist_id):
        """Obtener disponibilidad del especialista"""
        availability = Availability.objects.filter(
            specialist_id=specialist_id
        ).order_by("day_of_week", "start_time")

        serializer = AvailabilitySerializer(availability, many=True)

        return APIResponse.success(
            message="Availability retrieved", data=serializer.data
        )

    @api_error_handler
    @require_permissions([user_is_admin, user_is_specialist])
    def post(self, request, specialist_id):
        """Crear nuevo bloque de disponibilidad"""
        serializer = AvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Verificar permisos
        if request.user.user_type == "specialist":
            if request.user.specialist_profile.id != specialist_id:
                raise PermissionError("Cannot add availability for another specialist")

        # Usar servicio para crear
        availability = AvailabilityService.create_availability(
            specialist_id=specialist_id, **serializer.validated_data
        )

        return APIResponse.created(
            message="Availability created",
            data=AvailabilitySerializer(availability).data,
        )


class AvailableSlotsView(APIView):
    """
    GET /api/specialists/<id>/available-slots/
    Obtener slots disponibles para una fecha
    """

    permission_classes = [AllowAny]

    @api_error_handler
    def get(self, request, specialist_id):
        """Obtener slots disponibles"""
        date = request.query_params.get("date")
        service_id = request.query_params.get("service_id")

        if not date:
            raise ValidationError(detail="Date parameter is required")

        # Obtener duración del servicio
        service_duration = 60  # default 60 minutos
        if service_id:
            try:
                service = Service.objects.get(id=service_id)
                service_duration = service.duration_minutes
            except Service.DoesNotExist:
                pass

        # Usar servicio para obtener slots
        slots = AvailabilityService.get_available_slots(
            specialist_id=specialist_id, date=date, service_duration=service_duration
        )

        return APIResponse.success(message="Available slots retrieved", data=slots)


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
