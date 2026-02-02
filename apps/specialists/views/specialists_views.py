from django.http import Http404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import filters
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import PermissionDenied

from apps.core.decorators.error_handler import api_error_handler
from apps.core.exceptions.base_exceptions import (
    NotFoundError,
    PrivacyError,
    ValidationError,
)
from apps.core.responses.api_response import APIResponse
from ..models import Specialist
from ..serializers import (
    SpecialistSerializer,
    SpecialistDetailSerializer,
    SpecialistCreateSerializer,
    SpecialistUpdateSerializer,
    SpecialistSearchSerializer,
)
from ..services import SpecialistServiceLayer
from apps.core.permissions import IsAdminOrStaff, IsSpecialistOrStaff


class SpecialistViewSet(viewsets.ModelViewSet):
    """
    Unified ViewSet to handle all specialist operations
    """

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = {
        "specialization": ["exact"],
        "is_accepting_new_patients": ["exact"],
        "rating": ["gte", "lte"],
        "consultation_fee": ["gte", "lte"],
        "years_experience": ["gte", "lte"],
    }
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "qualifications",
        "bio",
    ]
    ordering_fields = [
        "rating",
        "consultation_fee",
        "years_experience",
    ]
    ordering = ["-rating"]

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in [
            "create",
            "destroy",
            "activate_specialist",
            "deactivate_specialist",
        ]:
            return [IsAdminOrStaff()]
        elif self.action in [
            "update",
            "partial_update",
            "activate_specialist",
            "deactivate_specialist",
        ]:
            return [IsSpecialistOrStaff()]
        elif self.action in [
            "list",
            "retrieve",
            "specialist_services",
            "available_slots",
            "by_specialization",
            "specialist_availability",
        ]:
            return [AllowAny()]

        return super().get_permissions()

    def get_queryset(self):
        # Allow inactive specialists for activate action
        if self.action == "activate_specialist":
            queryset = Specialist.objects.select_related("user").filter(
                user__is_active=True
            )
        else:
            queryset = Specialist.objects.select_related("user").filter(
                user__is_active=True, is_active=True  # Only show active specialists
            )

        # Apply search filters from query params
        params = self.request.query_params

        # Filter by service if provided
        service_id = params.get("service_id")
        if service_id:
            queryset = queryset.filter(
                services__service_id=service_id, services__is_available=True
            ).distinct()

        # Filter by min_rating
        min_rating = params.get("min_rating")
        if min_rating:
            queryset = queryset.filter(rating__gte=min_rating)

        # Filter by max_fee
        max_fee = params.get("max_fee")
        if max_fee:
            queryset = queryset.filter(consultation_fee__lte=max_fee)

        # Custom text search
        search = params.get("search")
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(user__email__icontains=search)
                | Q(qualifications__icontains=search)
                | Q(bio__icontains=search)
            )

        return queryset

    def get_serializer_class(self):
        """Return the appropriate serializer based on the action"""
        if self.action == "create":
            return SpecialistCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return SpecialistUpdateSerializer
        elif self.action == "retrieve":
            return SpecialistDetailSerializer
        return SpecialistSerializer

    @api_error_handler
    def list(self, request, *args, **kwargs):
        """List specialists with search and filters"""
        # Validate search parameters
        search_serializer = SpecialistSearchSerializer(data=request.query_params)
        search_serializer.is_valid(raise_exception=True)

        # Use service for business logic
        specialists, pagination = SpecialistServiceLayer.search_specialists(
            filters=search_serializer.validated_data,
            page=search_serializer.validated_data.get("page", 1),
            page_size=search_serializer.validated_data.get("page_size", 20),
        )

        serializer = self.get_serializer(specialists, many=True)

        return APIResponse.success(
            message="Specialists retrieved successfully",
            data=serializer.data,
            pagination=pagination,
        )

    @api_error_handler
    def retrieve(self, request, *args, **kwargs):
        """Get specialist details"""
        try:
            instance = self.get_object()
        except Http404:
            raise NotFoundError("Specialist not found")

        detail_result = SpecialistServiceLayer.get_specialist_detail(instance.id)
        specialist_data = detail_result["specialist"]
        stats = detail_result["stats"]

        serializer = self.get_serializer(specialist_data)
        data = serializer.data
        data["stats"] = stats

        return APIResponse.success(message="Specialist details retrieved", data=data)

    @api_error_handler
    def create(self, request, *args, **kwargs):
        """Create new specialist profile"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        specialist = SpecialistServiceLayer.create_specialist(
            **serializer.validated_data
        )

        return APIResponse.created(
            message="Specialist profile created successfully",
            data=SpecialistSerializer(specialist).data,
        )

    @api_error_handler
    def update(self, request, *args, **kwargs):
        """Update specialist profile"""
        instance = self.get_object()

        # Check permissions
        if request.user.user_type == "specialist":
            if not hasattr(request.user, "specialist_profile"):
                raise PrivacyError("User is not a specialist")
            if request.user.specialist_profile.id != instance.id:
                raise PrivacyError("Cannot update another specialist's profile")

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Use service for business logic
        specialist = SpecialistServiceLayer.update_specialist(
            specialist_id=instance.id, **serializer.validated_data
        )

        return APIResponse.success(
            message="Specialist profile updated",
            data=SpecialistSerializer(specialist).data,
        )

    @api_error_handler
    def destroy(self, request, *args, **kwargs):
        """Delete specialist profile"""
        try:
            instance = self.get_object()
        except Http404:
            raise NotFoundError("Specialist not found")

        # Check permissions
        if request.user.user_type not in ["admin", "staff"]:
            raise PermissionDenied(
                "Only admins or staff can delete specialist profiles"
            )

        # Use service for business logic
        SpecialistServiceLayer.delete_specialist(
            specialist_id=instance.id, deleted_by=request.user
        )

        return APIResponse.success(message="Specialist profile deleted successfully")

    @api_error_handler
    @action(detail=True, methods=["get"], url_path="services")
    def specialist_services(self, request, pk=None):
        """Get services offered by specialist"""
        specialist = self.get_object()

        # Get services with price overrides
        specialist_services = specialist.services.filter(
            is_available=True
        ).select_related("service")

        from ..serializers import SpecialistServiceSerializer

        serializer = SpecialistServiceSerializer(specialist_services, many=True)

        return APIResponse.success(
            message="Specialist services retrieved", data=serializer.data
        )

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="add-service")
    def add_service(self, request, pk=None):
        """Add service to specialist's offerings"""
        specialist = self.get_object()

        # Check permissions
        if not hasattr(request.user, "specialist_profile"):
            raise PrivacyError("User is not a specialist")
        if request.user.specialist_profile.id != specialist.id:
            raise PrivacyError("Cannot add services to another specialist")

        service_id = request.data.get("service_id")
        price_override = request.data.get("price_override")

        if not service_id:
            from rest_framework.exceptions import ValidationError

            raise ValidationError(detail="service_id is required")

        # Use service for business logic
        specialist_service = SpecialistServiceLayer.add_service_to_specialist(
            specialist_id=specialist.id,
            service_id=service_id,
            price_override=price_override,
        )

        from ..serializers import SpecialistServiceSerializer

        serializer = SpecialistServiceSerializer(specialist_service)

        return APIResponse.created(
            message="Service added to specialist", data=serializer.data
        )

    @api_error_handler
    @action(
        detail=True, methods=["delete"], url_path=r"remove-service/(?P<service_id>\d+)"
    )
    def remove_service(self, request, pk=None, service_id=None):
        """Remove service from specialist's offerings"""
        specialist = self.get_object()

        # Check permissions
        if request.user.user_type == "specialist":
            if not hasattr(request.user, "specialist_profile"):
                raise PrivacyError("User is not a specialist")
            if request.user.specialist_profile.id != specialist.id:
                raise PrivacyError("Cannot remove services from another specialist")
        elif request.user.user_type not in ["admin", "staff"]:
            raise PermissionDenied(
                "Only admins, staff, or specialists can remove services"
            )

        # Use service for business logic
        SpecialistServiceLayer.remove_service_from_specialist(
            specialist_id=specialist.id, service_id=service_id
        )

        return APIResponse.success(
            message="Service removed from specialist's offerings"
        )

    @api_error_handler
    @action(detail=True, methods=["get"], url_path="availability")
    def specialist_availability(self, request, pk=None):
        """Get specialist availability"""
        specialist = self.get_object()

        # Get current and future availability
        from django.utils import timezone
        from ..models import Availability

        availability = specialist.availability.filter(
            Q(valid_until__gte=timezone.now().date()) | Q(valid_until__isnull=True),
            is_recurring=True,
        ).order_by("day_of_week", "start_time")

        from ..serializers import AvailabilitySerializer

        serializer = AvailabilitySerializer(availability, many=True)

        return APIResponse.success(
            message="Specialist availability retrieved", data=serializer.data
        )

    @api_error_handler
    @action(detail=True, methods=["get"], url_path="available-slots/(?P<date>[^/.]+)")
    def available_slots(self, request, pk=None, date=None):
        """Get available time slots for a specific date"""
        specialist = self.get_object()

        # Use service for business logic
        slots = SpecialistServiceLayer.get_specialist_availability_slots(
            specialist_id=specialist.id, date=date
        )

        return APIResponse.success(message=f"Available slots for {date}", data=slots)

    @api_error_handler
    @action(detail=False, methods=["get"], url_path="by-specialization")
    def by_specialization(self, request):
        """List specialists grouped by specialization"""
        # Use service for business logic
        result = SpecialistServiceLayer.get_specialists_by_specialization()

        # Serialize specialists
        for specialization, data in result.items():
            if "top_specialists" in data:
                serializer = SpecialistSerializer(data["top_specialists"], many=True)
                data["top_specialists"] = serializer.data

        return APIResponse.success(
            message="Specialists grouped by specialization", data=result
        )

    @api_error_handler
    @api_error_handler
    @action(detail=True, methods=["post"], url_path="activate")
    def activate_specialist(self, request, pk=None):
        """Activate a deactivated specialist"""
        specialist = self.get_object()

        # Use service for business logic
        specialist = SpecialistServiceLayer.update_specialist(
            specialist_id=specialist.id, is_active=True, is_accepting_new_patients=True
        )

        return APIResponse.success(
            message="Specialist activated successfully",
            data=SpecialistSerializer(specialist).data,
        )

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate_specialist(self, request, pk=None):
        """Deactivate specialist (soft delete)"""
        specialist = self.get_object()

        # Check permissions
        if request.user.user_type not in ["admin", "staff"]:
            raise PermissionDenied("Only admins or staff can deactivate specialists")

        # Use service for business logic
        specialist = SpecialistServiceLayer.delete_specialist(
            specialist_id=specialist.id, deleted_by=request.user
        )

        return APIResponse.success(
            message="Specialist deactivated successfully",
            data=SpecialistSerializer(specialist).data,
        )
