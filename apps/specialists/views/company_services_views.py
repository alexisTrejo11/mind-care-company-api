from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema_view, extend_schema

from apps.core.decorators.error_handler import api_error_handler
from apps.core.decorators.rate_limit import rate_limit
from apps.core.responses.api_response import APIResponse
from apps.core.permissions import IsAdminOrStaff
from ..serializers import (
    ServiceSerializer,
    ServiceCreateSerializer,
    ServiceUpdateSerializer,
)
from ..filters import ServiceFilter
from ..services import CompanyServicesUseCases


@extend_schema_view(
    list=extend_schema(summary="List services", tags=["Services"]),
    retrieve=extend_schema(summary="Get service details", tags=["Services"]),
    create=extend_schema(summary="Create service (admin)", tags=["Services", "Admin"]),
    update=extend_schema(summary="Update service (admin)", tags=["Services", "Admin"]),
    partial_update=extend_schema(
        summary="Partial update service (admin)", tags=["Services", "Admin"]
    ),
    destroy=extend_schema(
        summary="Deactivate service (admin)", tags=["Services", "Admin"]
    ),
)
class ServiceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for healthcare services management.
    """

    queryset = CompanyServicesUseCases.get_base_queryset()
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = ServiceFilter
    ordering_fields = ["name", "category", "duration_minutes", "base_price"]
    ordering = ["name"]

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "reactivate",
        ]:
            return [IsAdminOrStaff()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.action == "create":
            return ServiceCreateSerializer
        if self.action in ["update", "partial_update"]:
            return ServiceUpdateSerializer
        return ServiceSerializer

    @api_error_handler
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return APIResponse.from_paginated_response(
                self.paginator,
                serializer.data,
                message="Services retrieved successfully",
            )

        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(
            message="Services retrieved successfully",
            data=serializer.data,
        )

    @api_error_handler
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        specialists = CompanyServicesUseCases.get_service_specialists(instance)

        serializer = self.get_serializer(instance)
        data = serializer.data
        data["offered_by"] = {
            "total_specialists": len(specialists),
            "specialists": specialists,
        }

        return APIResponse.success(message="Service details retrieved", data=data)

    @api_error_handler
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = CompanyServicesUseCases.create_service(**serializer.validated_data)

        return APIResponse.created(
            message="Service created successfully",
            data=ServiceSerializer(service).data,
        )

    @api_error_handler
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)

        updated_service = CompanyServicesUseCases.update_service(
            instance, **serializer.validated_data
        )

        return APIResponse.success(
            message="Service updated successfully",
            data=ServiceSerializer(updated_service).data,
        )

    @api_error_handler
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        updated_service = CompanyServicesUseCases.update_service(
            instance, **serializer.validated_data
        )

        return APIResponse.success(
            message="Service partially updated",
            data=ServiceSerializer(updated_service).data,
        )

    @api_error_handler
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        CompanyServicesUseCases.deactivate_service(
            instance, deactivated_by=request.user
        )
        return APIResponse.success(message="Service deactivated successfully")

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, pk=None):
        instance = self.get_object()
        reactivated = CompanyServicesUseCases.reactivate_service(
            instance, reactivated_by=request.user
        )
        return APIResponse.success(
            message="Service reactivated",
            data=ServiceSerializer(reactivated).data,
        )

    @api_error_handler
    @action(detail=False, methods=["get"], url_path="by-category")
    def by_category(self, request):
        result = CompanyServicesUseCases.get_services_by_category()
        return APIResponse.success(message="Services grouped by category", data=result)
