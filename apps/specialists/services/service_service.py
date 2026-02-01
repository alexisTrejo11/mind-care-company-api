from ..models import Service
from typing import List, Optional
from django.core.exceptions import ValidationError as DjangoValidationError
from core.exceptions.base_exceptions import ConflictError, ValidationError
import logging


logger = logging.getLogger(__name__)


class ServiceService:
    """Service management service"""

    @staticmethod
    def create_service(**kwargs) -> Service:
        # TODO: Add any additional business logic or validations here
        service = Service.objects.create(**kwargs)

        logger.info(f"Service created: {service.pk} - {service.name}")

        service.save()
        service.refresh_from_db()

        logger.info(f"Service persisted in database: {service.pk}")

        return service

    @staticmethod
    def update_service(service: Service, **kwargs) -> Service:
        for key, value in kwargs.items():
            setattr(service, key, value)

        logger.info(f"Updating service: {service.pk} - {service.name}")

        service.save()
        service.refresh_from_db()

        logger.info(f"Service updated in database: {service.pk}")

        return service

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
