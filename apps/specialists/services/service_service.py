from ..models import Service
from typing import List, Optional
from django.core.exceptions import ValidationError as DjangoValidationError
from core.exceptions.base_exceptions import ConflictError, ValidationError
import logging


logger = logging.getLogger(__name__)


class ServiceService:
    """Service management service"""

    @staticmethod
    def create_service(
        name: str, category: str, duration_minutes: int, base_price: float, **kwargs
    ) -> Service:
        """
        Create a new service
        """
        try:
            existing = Service.objects.filter(
                name__iexact=name, category=category
            ).exists()

            if existing:
                raise ConflictError(
                    detail="Service with this name and category already exists",
                    code="service_exists",
                )

            service = Service.objects.create(
                name=name,
                category=category,
                duration_minutes=duration_minutes,
                base_price=base_price,
                **kwargs,
            )

            logger.info(f"Service created: {service.pk} - {service.name}")

            return service

        except DjangoValidationError as e:
            raise ValidationError(detail=str(e))

    @staticmethod
    def get_services_by_category(
        category: Optional[str] = None, active_only: bool = True
    ) -> List[Service]:
        """
        Get services filtered by category and active status
        """
        queryset = Service.objects.all()

        if active_only:
            queryset = queryset.filter(is_active=True)

        if category:
            queryset = queryset.filter(category=category)

        return list(queryset.order_by("name"))
