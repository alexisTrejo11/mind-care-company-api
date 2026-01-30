import logging
from typing import Optional, Dict, Any, List, Tuple
from django.db import transaction
from django.db.models import Q, Avg, Count
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import get_user_model

from core.exceptions.base_exceptions import (
    ValidationError,
    NotFoundError,
    BusinessRuleError,
    ConflictError,
)

from ..models import Specialist, SpecialistService, Service
from ..serializers import SpecialistSearchSerializer

logger = logging.getLogger(__name__)
User = get_user_model()


class SpecialistServiceLayer:
    """Servicio principal para operaciones de especialistas"""

    @staticmethod
    @transaction.atomic
    def create_specialist(
        user_id: str,
        license_number: str,
        specialization: str,
        consultation_fee: float,
        **kwargs,
    ) -> Specialist:
        """
        Crear un nuevo especialista
        """
        try:
            # Validar usuario
            user = User.objects.get(user_id=user_id)

            if hasattr(user, "specialist_profile"):
                raise BusinessRuleError(
                    detail="User is already registered as a specialist",
                    code="user_already_specialist",
                )

            # Validar unicidad de licencia
            if Specialist.objects.filter(
                license_number__iexact=license_number
            ).exists():
                raise ConflictError(
                    detail="License number already registered", code="license_exists"
                )

            specialist = Specialist.objects.create(
                user=user,
                license_number=license_number.upper(),
                specialization=specialization,
                consultation_fee=consultation_fee,
                **kwargs,
            )

            logger.info(f"Specialist created: {specialist.pk} - {user.email}")

            return specialist

        except User.DoesNotExist:
            raise NotFoundError(detail="User not found")
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e))
        except Exception as e:
            logger.error(f"Error creating specialist: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def update_specialist(specialist_id: int, **update_data) -> Specialist:
        """
        Actualizar información de especialista
        """
        try:
            specialist = Specialist.objects.get(id=specialist_id)

            # Campos que no se pueden actualizar directamente
            restricted_fields = ["user", "rating"]
            for field in restricted_fields:
                update_data.pop(field, None)

            # Validar unicidad de licencia si se está actualizando
            if "license_number" in update_data:
                license_number = update_data["license_number"].upper()
                if (
                    Specialist.objects.filter(license_number__iexact=license_number)
                    .exclude(id=specialist_id)
                    .exists()
                ):
                    raise ConflictError(
                        detail="License number already in use", code="license_in_use"
                    )
                update_data["license_number"] = license_number

            # Actualizar
            for field, value in update_data.items():
                setattr(specialist, field, value)

            specialist.full_clean()
            specialist.save()

            logger.info(f"Specialist updated: {specialist.pk}")

            return specialist

        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e))

    @staticmethod
    def get_specialist_detail(specialist_id: int) -> Dict[str, Any]:
        """
        Get detailed information of a specialist
        """
        try:
            specialist = Specialist.objects.select_related("user").get(id=specialist_id)

            # Calcular estadísticas
            total_appointments = getattr(specialist, "appointment_count", 0)
            avg_rating = getattr(specialist, "avg_rating", 0)

            return {
                "specialist": specialist,
                "stats": {
                    "total_appointments": total_appointments,
                    "avg_rating": float(avg_rating),
                    "services_count": specialist.services.count(),
                    "availability_slots": specialist.availability.count(),
                },
            }

        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")

    @staticmethod
    def search_specialists(
        filters: Dict[str, Any], page: int = 1, page_size: int = 20
    ) -> Tuple[List[Specialist], Dict[str, Any]]:
        """
        Search specialists with advanced filters
        """
        try:
            queryset = Specialist.objects.select_related("user").filter(
                user__is_active=True
            )

            # Apply filters
            if specialization := filters.get("specialization"):
                queryset = queryset.filter(specialization=specialization)

            if min_experience := filters.get("min_experience"):
                queryset = queryset.filter(years_experience__gte=min_experience)

            if max_fee := filters.get("max_fee"):
                queryset = queryset.filter(consultation_fee__lte=max_fee)

            if accepting_new := filters.get("accepting_new_patients"):
                queryset = queryset.filter(is_accepting_new_patients=accepting_new)

            if min_rating := filters.get("min_rating"):
                queryset = queryset.filter(rating__gte=min_rating)

            # Text search
            if search_query := filters.get("search"):
                queryset = queryset.filter(
                    Q(user__first_name__icontains=search_query)
                    | Q(user__last_name__icontains=search_query)
                    | Q(specialization__icontains=search_query)
                    | Q(bio__icontains=search_query)
                )

            # Filter by service category
            if service_category := filters.get("service_category"):
                queryset = queryset.filter(
                    services__service__category=service_category,
                    services__is_available=True,
                ).distinct()

            # Ordenamiento
            queryset = queryset.order_by("-rating", "user__last_name")

            # Paginación
            total = queryset.count()
            start = (page - 1) * page_size
            end = start + page_size

            specialists = queryset[start:end]

            pagination = {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
                "has_next": end < total,
                "has_previous": page > 1,
            }

            return list(specialists), pagination

        except Exception as e:
            logger.error(f"Error searching specialists: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def add_service_to_specialist(
        specialist_id: int, service_id: int, price_override: Optional[float] = None
    ) -> SpecialistService:
        """
        Add service to specialist
        """
        try:
            specialist = Specialist.objects.get(id=specialist_id)
            service = Service.objects.get(id=service_id, is_active=True)

            if SpecialistService.objects.filter(
                specialist=specialist, service=service
            ).exists():
                raise ConflictError(
                    detail="Service already assigned to specialist",
                    code="service_already_assigned",
                )

            specialist_service = SpecialistService.objects.create(
                specialist=specialist,
                service=service,
                price_override=price_override,
                is_available=True,
            )

            logger.info(f"Service {service_id} added to specialist {specialist_id}")

            return specialist_service

        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")
        except Service.DoesNotExist:
            raise NotFoundError(detail="Service not found or inactive")
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e))

    @staticmethod
    def update_specialist_rating(specialist_id: int) -> Specialist:
        """
        Recalculate the average rating of a specialist
        """
        try:
            specialist = Specialist.objects.get(id=specialist_id)

            # Calcular nuevo rating promedio
            from apps.appointments.models import Appointment

            # Ejemplo: calcular basado en reviews de appointments
            # Esto depende de cómo manejes las reviews
            # Por ahora, es un placeholder

            return specialist

        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")
