from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Count, Avg, Sum

from core.decorators.error_handler import api_error_handler
from core.responses.api_response import APIResponse
from core.permissions import IsAdminOrStaff
from ..models import Specialist, Service, SpecialistService
from ..serializers import (
    ServiceSerializer,
    ServiceCreateSerializer,
    ServiceUpdateSerializer,
    ServiceSearchSerializer,
    ServiceStatsSerializer,
    SpecialistServiceSerializer,
    SpecialistSerializer,
)
from core.exceptions.base_exceptions import NotFoundError, ValidationError

from ..services import ServiceService


class ServiceViewSet(viewsets.ModelViewSet):
    """
    Unified ViewSet to handle all service operations
    """

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = {
        "category": ["exact"],
        "is_active": ["exact"],
        "duration_minutes": ["gte", "lte"],
        "base_price": ["gte", "lte"],
    }
    search_fields = [
        "name",
        "description",
        "category",
    ]
    ordering_fields = [
        "name",
        "category",
        "duration_minutes",
        "base_price",
    ]
    ordering = ["name"]

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "reactivate",
            "stats",
            "add_to_specialist",
        ]:
            return [IsAdminOrStaff()]
        else:
            return [AllowAny()]

    def get_queryset(self):
        queryset = Service.objects.all()

        # Apply custom filters
        params = self.request.query_params

        # Filter by active_only
        active_only = params.get("active_only", "true").lower() == "true"
        if active_only:
            queryset = queryset.filter(is_active=True)

        # Filter by min_duration
        min_duration = params.get("min_duration")
        if min_duration:
            queryset = queryset.filter(duration_minutes__gte=min_duration)

        # Filter by max_duration
        max_duration = params.get("max_duration")
        if max_duration:
            queryset = queryset.filter(duration_minutes__lte=max_duration)

        # Filter by min_price
        min_price = params.get("min_price")
        if min_price:
            queryset = queryset.filter(base_price__gte=min_price)

        # Filter by max_price
        max_price = params.get("max_price")
        if max_price:
            queryset = queryset.filter(base_price__lte=max_price)

        return queryset

    def get_serializer_class(self):
        """Return the appropriate serializer based on the action"""
        if self.action == "create":
            return ServiceCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return ServiceUpdateSerializer
        return ServiceSerializer

    @api_error_handler
    def list(self, request, *args, **kwargs):
        """List services with search and filters"""
        # Validate search parameters
        search_serializer = ServiceSearchSerializer(data=request.query_params)
        search_serializer.is_valid(raise_exception=True)

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(
            message="Services retrieved successfully", data=serializer.data
        )

    @api_error_handler
    def retrieve(self, request, *args, **kwargs):
        """Get service details with specialists who offer it"""
        instance = self.get_object()

        # Get specialists offering this service
        specialist_services = instance.specialists.filter(
            is_available=True
        ).select_related("specialist", "specialist__user")

        specialist_services_data = SpecialistServiceSerializer(
            specialist_services, many=True
        ).data

        serializer = self.get_serializer(instance)
        data = serializer.data
        data["offered_by"] = {
            "total_specialists": specialist_services.count(),
            "specialists": specialist_services_data,
        }

        return APIResponse.success(message="Service details retrieved", data=data)

    @api_error_handler
    def create(self, request, *args, **kwargs):
        """Create new service using ServiceService"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serviceCreated = ServiceService.create_service(**serializer.validated_data)

        return APIResponse.created(
            message="Service created successfully",
            data=ServiceSerializer(serviceCreated).data,
        )

    @api_error_handler
    def update(self, request, *args, **kwargs):
        """Update service"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        serviceUpdated = ServiceService.update_service(
            instance, **serializer.validated_data
        )

        return APIResponse.success(
            message="Service updated successfully",
            data=ServiceSerializer(serviceUpdated).data,
        )

    @api_error_handler
    def destroy(self, request, *args, **kwargs):
        """Deactivate service"""
        instance = self.get_object()

        # TODO: Move to ServiceService if more logic is added
        instance.is_active = False
        instance.save()

        # Also deactivate all specialist-service relationships
        SpecialistService.objects.filter(service=instance).update(is_available=False)

        return APIResponse.success(message="Service deactivated successfully")

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, pk=None):
        """Reactivate a deactivated service"""
        instance = self.get_object()
        instance.is_active = True
        instance.save()

        return APIResponse.success(
            message="Service reactivated successfully",
            data=ServiceSerializer(instance).data,
        )

    @api_error_handler
    @action(detail=True, methods=["get"], url_path="specialists")
    def service_specialists(self, request, pk=None):
        """Get all specialists offering this service"""
        service = self.get_object()

        specialist_services = service.specialists.filter(
            is_available=True
        ).select_related("specialist", "specialist__user")

        # Get specialist details
        specialists_data = []
        for ss in specialist_services:
            specialist = ss.specialist
            specialists_data.append(
                {
                    "specialist_id": specialist.id,
                    "name": specialist.user.get_full_name(),
                    "specialization": specialist.specialization,
                    "rating": float(specialist.rating),
                    "price": float(ss.get_price()),
                    "years_experience": specialist.years_experience,
                }
            )

        return APIResponse.success(
            message=f"Specialists offering {service.name}",
            data={
                "service_id": service.id,
                "service_name": service.name,
                "specialists": specialists_data,
                "total_specialists": len(specialists_data),
            },
        )

    @api_error_handler
    @action(detail=False, methods=["get"], url_path="by-category")
    def by_category(self, request):
        """List services grouped by category"""
        # Get all categories with counts
        categories = (
            Service.objects.filter(is_active=True)
            .values("category")
            .annotate(
                count=Count("id"),
                avg_duration=Avg("duration_minutes"),
                avg_price=Avg("base_price"),
            )
            .order_by("category")
        )

        # Get services for each category
        result = {}
        for cat in categories:
            category = cat["category"]
            services = Service.objects.filter(category=category, is_active=True)[
                :5
            ]  # Limit to 5 per category

            serializer = ServiceSerializer(services, many=True)
            result[category] = {
                "display_name": dict(Service.CATEGORY_CHOICES).get(category, category),
                "count": cat["count"],
                "avg_duration": float(cat["avg_duration"] or 0),
                "avg_price": float(cat["avg_price"] or 0),
                "services": serializer.data,
            }

        return APIResponse.success(message="Services grouped by category", data=result)

    @api_error_handler
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """Get service statistics"""

        # Validate parameters
        stats_serializer = ServiceStatsSerializer(data=request.query_params)
        stats_serializer.is_valid(raise_exception=True)

        period = stats_serializer.validated_data["period"]
        include_inactive = stats_serializer.validated_data["include_inactive"]

        queryset = Service.objects.all()
        if not include_inactive:
            queryset = queryset.filter(is_active=True)

        # Calculate statistics
        total_services = queryset.count()
        total_active = Service.objects.filter(is_active=True).count()

        by_category = (
            queryset.values("category")
            .annotate(
                count=Count("id"),
                avg_duration=Avg("duration_minutes"),
                avg_price=Avg("base_price"),
                total_price=Sum("base_price"),
            )
            .order_by("-count")
        )

        # Most popular services by specialist count
        popular_services = (
            Service.objects.filter(is_active=True)
            .annotate(
                specialist_count=Count(
                    "specialists", filter=Q(specialists__is_available=True)
                )
            )
            .order_by("-specialist_count")[:10]
        )

        popular_services_data = ServiceSerializer(popular_services, many=True).data

        stats = {
            "period": period,
            "summary": {
                "total_services": total_services,
                "total_active": total_active,
                "total_inactive": total_services - total_active,
                "inactive_percentage": round(
                    (
                        ((total_services - total_active) / total_services * 100)
                        if total_services > 0
                        else 0
                    ),
                    2,
                ),
            },
            "by_category": list(by_category),
            "most_popular": popular_services_data,
        }

        return APIResponse.success(message="Service statistics retrieved", data=stats)

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="add-to-specialist")
    def add_to_specialist(self, request, pk=None):
        """Add service to specialist's offerings"""
        service = self.get_object()

        # Validate specialist exists
        specialist_id = request.data.get("specialist_id")
        if not specialist_id:
            raise ValidationError(detail="specialist_id is required")

        try:
            specialist = Specialist.objects.get(id=specialist_id)
        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")

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

        # Check if already exists
        if SpecialistService.objects.filter(
            specialist=specialist, service=service
        ).exists():
            raise ValidationError(detail="Specialist already offers this service")

        # Create specialist-service relationship
        price_override = request.data.get("price_override")
        specialist_service = SpecialistService.objects.create(
            specialist=specialist,
            service=service,
            price_override=price_override,
            is_available=True,
        )

        return APIResponse.created(
            message=f"Service '{service.name}' added to specialist",
            data=SpecialistServiceSerializer(specialist_service).data,
        )
