import logging
from typing import Dict, List, Optional
from django.db.models.query import QuerySet
from decimal import Decimal

from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Avg, Min, Max, Sum

from ..models import Service, SpecialistService
from apps.core.exceptions.base_exceptions import ConflictError, ValidationError

logger = logging.getLogger(__name__)


class CompanyServicesUseCases:
    """Service manager for service business logic"""

    MIN_DURATION_MINUTES = 5
    MAX_DURATION_MINUTES = 480
    MIN_SERVICE_PRICE = Decimal("5.00")
    MAX_SERVICE_PRICE = Decimal("5000.00")

    @staticmethod
    def get_base_queryset() -> "QuerySet[Service]":
        """Base queryset for services"""
        return Service.objects.all()

    @staticmethod
    def get_services_by_category(
        category: Optional[str] = None, active_only: bool = True
    ) -> Dict:
        """Get services grouped by category with statistics"""
        queryset = CompanyServicesUseCases.get_base_queryset()
        if active_only:
            queryset = queryset.filter(is_active=True)
        if category:
            queryset = queryset.filter(category=category)

        categories = (
            queryset.values("category")
            .annotate(
                count=Count("id"),
                avg_duration=Avg("duration_minutes"),
                avg_price=Avg("base_price"),
                min_price=Min("base_price"),
                max_price=Max("base_price"),
                specialist_count=Count(
                    "specialists", filter=Q(specialists__is_available=True)
                ),
            )
            .order_by("category")
        )

        result = {}
        for cat in categories:
            category_name = cat["category"]
            services = (
                queryset.filter(category=category_name)
                .annotate(
                    specialist_count=Count(
                        "specialists", filter=Q(specialists__is_available=True)
                    )
                )
                .order_by("-specialist_count", "name")[:5]
            )

            result[category_name] = {
                "display_name": dict(Service.CATEGORY_CHOICES).get(
                    category_name, category_name
                ),
                "count": cat["count"],
                "avg_duration": float(cat["avg_duration"] or 0),
                "avg_price": float(cat["avg_price"] or 0),
                "price_range": {
                    "min": float(cat["min_price"] or 0),
                    "max": float(cat["max_price"] or 0),
                },
                "specialist_count": cat["specialist_count"],
                "top_services": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "description": s.description,
                        "duration_minutes": s.duration_minutes,
                        "base_price": float(s.base_price),
                        "specialist_count": s.specialist_count,
                    }
                    for s in services
                ],
            }

        return result

    @staticmethod
    def get_service_specialists(service: Service) -> List[Dict]:
        """Get specialists offering this service"""
        specialist_services = (
            service.specialists.filter(is_available=True)
            .select_related("specialist", "specialist__user")
            .order_by("-specialist__rating")
        )

        data = [
            {
                "specialist_id": ss.specialist.id,
                "name": ss.specialist.user.get_full_name(),
                "specialization": ss.specialist.specialization,
                "rating": float(ss.specialist.rating),
                "price": float(ss.get_price()),
                "years_experience": ss.specialist.years_experience,
            }
            for ss in specialist_services
        ]

        return data

    @classmethod
    @transaction.atomic
    def create_service(cls, **validated_data):
        """Create a new service with business logic validation"""
        name = validated_data.get("name")
        category = validated_data.get("category")
        duration_minutes = validated_data.get("duration_minutes")
        base_price = validated_data.get("base_price")

        # Validations
        name = cls.validate_service_name(name)
        category = cls.validate_service_category(category)
        duration_minutes = cls.validate_service_duration(duration_minutes)
        base_price = cls.validate_service_price(base_price)

        if Service.objects.filter(name=name, category=category).exists():
            raise ConflictError(
                detail=f"Service '{name}' already exists in category '{category}'"
            )

        service = Service.objects.create(
            name=name,
            category=category,
            duration_minutes=duration_minutes,
            base_price=base_price,
            description=validated_data.get("description", ""),
            is_active=True,
        )

        logger.info(f"Service created: {service.id} - {service.name}")
        return service

    @classmethod
    @transaction.atomic
    def update_service(cls, service: Service, **validated_data):
        """Update service with business logic validation"""
        if "name" in validated_data or "category" in validated_data:
            new_name = validated_data.get("name", service.name)
            new_category = validated_data.get("category", service.category)

            if new_name != service.name or new_category != service.category:
                if (
                    Service.objects.filter(name=new_name, category=new_category)
                    .exclude(id=service.id)
                    .exists()
                ):
                    raise ConflictError(
                        detail=f"Service '{new_name}' already exists in category '{new_category}'"
                    )

        if "duration_minutes" in validated_data:
            validated_data["duration_minutes"] = cls.validate_service_duration(
                validated_data["duration_minutes"]
            )

        if "base_price" in validated_data:
            validated_data["base_price"] = cls.validate_service_price(
                validated_data["base_price"]
            )

        for field, value in validated_data.items():
            setattr(service, field, value)

        service.save()
        logger.info(f"Service updated: {service.id} - {service.name}")
        return service

    @classmethod
    @transaction.atomic
    def deactivate_service(cls, service: Service, deactivated_by=None):
        """Deactivate service (soft delete)"""
        # Business rule check
        cls.can_deactivate_service(service)

        service.is_active = False
        service.save()

        SpecialistService.objects.filter(service=service).update(is_available=False)

        logger.info(f"Service deactivated: {service.id} - {service.name}")

        return service

    @staticmethod
    def reactivate_service(service: Service, reactivated_by=None):
        """Reactivate a deactivated service"""
        if service.is_active:
            raise ConflictError(detail="Service is already active")

        service.is_active = True
        service.save()

        logger.info(f"Service reactivated: {service.id} - {service.name}")

        return service

    @classmethod
    def can_deactivate_service(cls, service: Service):
        """Check if a service can be deactivated based on business rules"""
        active_specialists = SpecialistService.objects.filter(
            service=service, is_available=True
        ).count()
        if active_specialists > 0:
            raise ConflictError(
                detail="Cannot deactivate service with active specialists offering it"
            )

    @staticmethod
    def validate_service_name(name, exclude_service_id=None):
        """Validate service name format and uniqueness within category"""
        if not name or len(name.strip()) < 3:
            raise ValidationError(
                detail="Service name must be at least 3 characters long"
            )

        # Check for profanity or inappropriate content (placeholder)
        inappropriate_words = ["badword1", "badword2"]  # This would come from a list
        if any(word in name.lower() for word in inappropriate_words):
            raise ValidationError(detail="Service name contains inappropriate content")

        return name.strip()

    @staticmethod
    def validate_service_duration(duration_minutes):
        """Validate service duration"""
        if duration_minutes < CompanyServicesUseCases.MIN_DURATION_MINUTES:
            raise ValidationError(
                detail=f"Service duration must be at least {CompanyServicesUseCases.MIN_DURATION_MINUTES} minutes"
            )

        if duration_minutes > CompanyServicesUseCases.MAX_DURATION_MINUTES:
            raise ValidationError(
                detail=f"Service duration cannot exceed {CompanyServicesUseCases.MAX_DURATION_MINUTES} minutes"
            )

        # Validate duration is in standard increments (15, 30, 45, 60)
        if duration_minutes % 15 != 0:
            raise ValidationError(
                detail="Service duration must be in 15-minute increments (15, 30, 45, 60, etc.)"
            )

        return duration_minutes

    @staticmethod
    def validate_service_price(price):
        """Validate service price"""
        if price < CompanyServicesUseCases.MIN_SERVICE_PRICE:
            raise ValidationError(
                detail=f"Service price cannot be less than ${CompanyServicesUseCases.MIN_SERVICE_PRICE}"
            )

        if price > CompanyServicesUseCases.MAX_SERVICE_PRICE:
            raise ValidationError(
                detail=f"Service price cannot exceed ${CompanyServicesUseCases.MAX_SERVICE_PRICE}"
            )

        # Price should be reasonable (no crazy amounts)
        if price > Decimal("1000.00") and price % Decimal("100.00") != 0:
            raise ValidationError(
                detail="Services over $1000 should be in $100 increments"
            )

        return price

    @staticmethod
    def validate_service_category(category):
        """Validate service category"""
        valid_categories = dict(Service.CATEGORY_CHOICES).keys()
        if category not in valid_categories:
            raise ValidationError(
                detail=f"Invalid service category. Must be one of: {', '.join(valid_categories)}"
            )

        return category

    @classmethod
    def get_services_grouped_by_category(cls):
        """Get services grouped by category with statistics"""
        categories = (
            Service.objects.filter(is_active=True)
            .values("category")
            .annotate(
                count=Count("id"),
                avg_duration=Avg("duration_minutes"),
                avg_price=Avg("base_price"),
                min_price=Min("base_price"),
                max_price=Max("base_price"),
                specialist_count=Count(
                    "specialists",
                    distinct=True,
                    filter=Q(specialists__is_available=True),
                ),
            )
            .order_by("category")
        )

        result = {}
        for cat in categories:
            category = cat["category"]

            # Get top services in this category
            services = (
                Service.objects.filter(category=category, is_active=True)
                .annotate(
                    specialist_count=Count(
                        "specialists", filter=Q(specialists__is_available=True)
                    )
                )
                .order_by("-specialist_count", "name")[:5]
            )

            result[category] = {
                "display_name": dict(Service.CATEGORY_CHOICES).get(category, category),
                "count": cat["count"],
                "avg_duration": float(cat["avg_duration"] or 0),
                "avg_price": float(cat["avg_price"] or 0),
                "price_range": {
                    "min": float(cat["min_price"] or 0),
                    "max": float(cat["max_price"] or 0),
                },
                "specialist_count": cat["specialist_count"],
                "top_services": [
                    {
                        "id": service.id,
                        "name": service.name,
                        "description": service.description,
                        "duration_minutes": service.duration_minutes,
                        "base_price": float(service.base_price),
                        "specialist_count": service.specialist_count,
                    }
                    for service in services
                ],
            }

        return result

    @classmethod
    def update_service_price_for_specialist(
        cls, specialist_service, new_price_override, updated_by=None
    ):
        """Update price override for specialist's service"""

        # Validate new price
        if new_price_override is not None and new_price_override < 0:
            raise ValidationError(detail="Price cannot be negative")

        service = specialist_service.service

        # Validate price is reasonable
        if new_price_override:
            if new_price_override > service.base_price * 3:
                raise ValidationError(
                    detail="Price override cannot exceed 3 times the base price"
                )

            if new_price_override < service.base_price * Decimal("0.5"):
                raise ValidationError(
                    detail="Price override cannot be less than 50% of base price"
                )

        # Store old price for audit
        old_price = specialist_service.price_override

        # Update price
        specialist_service.price_override = new_price_override
        specialist_service.save()

        logger.info(f"Service price updated for specialist: {specialist_service.id}")

        # Log price change (placeholder)
        # ServiceAuditService.log_price_change(specialist_service, old_price, new_price_override, updated_by)

        return specialist_service

    @classmethod
    def get_service_statistics(cls, period="month", include_inactive=False):
        """Get service statistics for the given period"""
        # Define date range if needed (for appointment-based stats)
        now = timezone.now()

        # Base queryset
        queryset = Service.objects.all()
        if not include_inactive:
            queryset = queryset.filter(is_active=True)

        # Service count statistics
        total_services = queryset.count()
        total_active = Service.objects.filter(is_active=True).count()

        # Category distribution
        by_category = (
            queryset.values("category")
            .annotate(
                count=Count("id"),
                avg_duration=Avg("duration_minutes"),
                avg_price=Avg("base_price"),
                total_price=Sum("base_price"),
                min_price=Min("base_price"),
                max_price=Max("base_price"),
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

        # Services with no specialists
        services_without_specialists = Service.objects.filter(
            is_active=True, specialists__isnull=True
        ).count()

        # Services with price variations
        services_with_price_variations = (
            Service.objects.filter(
                is_active=True, specialists__price_override__isnull=False
            )
            .distinct()
            .count()
        )

        # Average metrics
        avg_metrics = queryset.aggregate(
            avg_duration=Avg("duration_minutes"),
            avg_price=Avg("base_price"),
            total_revenue_potential=Sum("base_price"),  # Placeholder for actual revenue
        )

        return {
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
                "services_without_specialists": services_without_specialists,
                "services_with_price_variations": services_with_price_variations,
            },
            "category_distribution": list(by_category),
            "popular_services": [
                {
                    "id": service.id,
                    "name": service.name,
                    "category": service.category,
                    "specialist_count": service.specialist_count,
                    "base_price": float(service.base_price),
                }
                for service in popular_services
            ],
            "averages": {
                "avg_duration_minutes": float(avg_metrics["avg_duration"] or 0),
                "avg_price": float(avg_metrics["avg_price"] or 0),
                "total_revenue_potential": float(
                    avg_metrics["total_revenue_potential"] or 0
                ),
            },
        }
