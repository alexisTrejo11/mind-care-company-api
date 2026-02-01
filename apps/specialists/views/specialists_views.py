from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from core.decorators.error_handler import api_error_handler
from core.responses.api_response import APIResponse
from core.exceptions.base_exceptions import ValidationError

from ..models import Specialist, SpecialistService
from ..serializers import (
    SpecialistSerializer,
    SpecialistDetailSerializer,
    SpecialistCreateSerializer,
    SpecialistUpdateSerializer,
    SpecialistSearchSerializer,
    SpecialistServiceSerializer,
    SpecialistServiceCreateSerializer,
)

# Placeholder for service - will implement later
# from .services import SpecialistService


class SpecialistViewSet(viewsets.ModelViewSet):
    """
    Unified ViewSet to handle all specialist operations
    """

    permission_classes = [AllowAny]  # List/retrieve open to all
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
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = Specialist.objects.select_related("user").filter(
            user__is_active=True
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

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(
            message="Specialists retrieved successfully", data=serializer.data
        )

    @api_error_handler
    def retrieve(self, request, *args, **kwargs):
        """Get specialist details"""
        instance = self.get_object()

        # Get statistics (placeholder - will move to service)
        stats = {
            "total_appointments": 0,  # Placeholder
            "avg_rating": float(instance.rating),
            "patient_count": 0,  # Placeholder
        }

        serializer = self.get_serializer(instance)
        data = serializer.data
        data["stats"] = stats

        return APIResponse.success(message="Specialist details retrieved", data=data)

    @api_error_handler
    def create(self, request, *args, **kwargs):
        """Create new specialist profile"""
        # Check permissions
        if not request.user.user_type in ["admin", "staff"]:
            raise PermissionDenied(
                "Only admins or staff can create specialist profiles"
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Placeholder for service call
        # specialist = SpecialistService.create_specialist(**serializer.validated_data)
        specialist = serializer.save()

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
                raise PermissionDenied("User is not a specialist")
            if request.user.specialist_profile.id != instance.id:
                raise PermissionDenied("Cannot update another specialist's profile")
        elif request.user.user_type not in ["admin", "staff"]:
            raise PermissionDenied(
                "Only admins, staff, or specialists can update profiles"
            )

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Placeholder for service call
        # specialist = SpecialistService.update_specialist(instance.id, **serializer.validated_data)
        specialist = serializer.save()

        return APIResponse.success(
            message="Specialist profile updated",
            data=SpecialistSerializer(specialist).data,
        )

    @api_error_handler
    def destroy(self, request, *args, **kwargs):
        """Delete specialist profile"""
        instance = self.get_object()

        # Check permissions
        if request.user.user_type not in ["admin", "staff"]:
            raise PermissionDenied(
                "Only admins or staff can delete specialist profiles"
            )

        # Placeholder for service call
        # SpecialistService.delete_specialist(instance.id, deleted_by=request.user)
        instance.delete()

        return APIResponse.success(message="Specialist profile deleted successfully")

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
    @action(detail=False, methods=["get"], url_path="search")
    def advanced_search(self, request, *args, **kwargs):
        """Advanced search endpoint with custom parameters"""
        return self.list(request, *args, **kwargs)

    @api_error_handler
    @action(detail=False, methods=["get"], url_path="by-specialization")
    def by_specialization(self, request):
        """List specialists grouped by specialization"""
        # Get all specializations with counts
        from django.db.models import Count

        specializations = (
            Specialist.objects.values("specialization")
            .annotate(count=Count("id"))
            .order_by("specialization")
        )

        # Get specialists for each specialization
        result = {}
        for spec in specializations:
            specialization = spec["specialization"]
            specialists = Specialist.objects.filter(
                specialization=specialization, is_accepting_new_patients=True
            ).select_related("user")[
                :5
            ]  # Limit to 5 per specialization

            serializer = SpecialistSerializer(specialists, many=True)
            result[specialization] = {
                "count": spec["count"],
                "specialists": serializer.data,
            }

        return APIResponse.success(
            message="Specialists grouped by specialization", data=result
        )

    # Specialist Service Relationship Endpoints Placeholder
    @api_error_handler
    @action(detail=True, methods=["get"], url_path="services")
    def specialist_services(self, request, pk=None):
        """Get services offered by specialist"""
        specialist = self.get_object()

        # Get services with price overrides
        specialist_services = specialist.services.filter(
            is_available=True
        ).select_related("service")

        serializer = SpecialistServiceSerializer(specialist_services, many=True)

        return APIResponse.success(
            message="Specialist services retrieved", data=serializer.data
        )

    # TODO: Implement Service and improve permission checks

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="add-service")
    def add_service(self, request, pk=None):
        """Add service to specialist's offerings"""
        specialist = self.get_object()

        # Check permissions
        if request.user.user_type == "specialist":
            if not hasattr(request.user, "specialist_profile"):
                raise PermissionDenied("User is not a specialist")
            if request.user.specialist_profile.id != specialist.id:
                raise PermissionDenied("Cannot add services to another specialist")
        elif request.user.user_type not in ["admin", "staff"]:
            raise PermissionDenied(
                "Only admins, staff, or specialists can add services"
            )

        serializer = SpecialistServiceCreateSerializer(
            data=request.data,
            context={"request": request, "specialist_id": specialist.id},
        )
        serializer.is_valid(raise_exception=True)

        # Create specialist-service relationship
        specialist_service = SpecialistService.objects.create(
            specialist=specialist,
            service=serializer.validated_data["service"],
            price_override=serializer.validated_data.get("price_override"),
            is_available=True,
        )

        return APIResponse.created(
            message="Service added to specialist",
            data=SpecialistServiceSerializer(specialist_service).data,
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
                raise PermissionDenied("User is not a specialist")
            if request.user.specialist_profile.id != specialist.id:
                raise PermissionDenied("Cannot remove services from another specialist")
        elif request.user.user_type not in ["admin", "staff"]:
            raise PermissionDenied(
                "Only admins, staff, or specialists can remove services"
            )

        specialist_service = SpecialistService.objects.get(
            specialist=specialist, service_id=service_id
        )
        # Instead of deleting, mark as unavailable
        specialist_service.is_available = False
        specialist_service.save()

        return APIResponse.success(
            message="Service removed from specialist's offerings"
        )

    @api_error_handler
    @action(
        detail=True,
        methods=["patch"],
        url_path=r"update-service-price/(?P<service_id>\d+)",
    )
    def update_service_price(self, request, pk=None, service_id=None):
        """Update price override for specialist's service"""
        specialist = self.get_object()

        # Check permissions
        if request.user.user_type == "specialist":
            if not hasattr(request.user, "specialist_profile"):
                raise PermissionDenied("User is not a specialist")
            if request.user.specialist_profile.id != specialist.id:
                raise PermissionDenied("Cannot update services for another specialist")
        elif request.user.user_type not in ["admin", "staff"]:
            raise PermissionDenied(
                "Only admins, staff, or specialists can update service prices"
            )

        specialist_service = SpecialistService.objects.get(
            specialist=specialist, service_id=service_id
        )
        price_override = request.data.get("price_override")

        # Validate price override
        if price_override is not None and price_override < 0:
            raise ValidationError(detail="Price cannot be negative")

        specialist_service.price_override = price_override
        specialist_service.save()

        return APIResponse.success(
            message="Service price updated",
            data=SpecialistServiceSerializer(specialist_service).data,
        )
