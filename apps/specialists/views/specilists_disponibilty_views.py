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
