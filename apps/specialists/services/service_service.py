from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Avg, Sum, Min, Max
from django.db.models.functions import TruncDate, TruncMonth
from decimal import Decimal
import logging

from ..models import Service, SpecialistService, Specialist
from apps.appointments.models import Appointment
from apps.core.exceptions.base_exceptions import (
    BusinessRuleError,
    ValidationError,
    ConflictError,
)

logger = logging.getLogger(__name__)


class ServiceServiceLayer:
    """Service layer for service business logic"""

    # Minimum service duration (5 minutes)
    MIN_DURATION_MINUTES = 5

    # Maximum service duration (8 hours)
    MAX_DURATION_MINUTES = 480

    # Minimum service price
    MIN_SERVICE_PRICE = Decimal("5.00")

    # Maximum service price
    MAX_SERVICE_PRICE = Decimal("5000.00")

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
        if duration_minutes < ServiceServiceLayer.MIN_DURATION_MINUTES:
            raise ValidationError(
                detail=f"Service duration must be at least {ServiceServiceLayer.MIN_DURATION_MINUTES} minutes"
            )

        if duration_minutes > ServiceServiceLayer.MAX_DURATION_MINUTES:
            raise ValidationError(
                detail=f"Service duration cannot exceed {ServiceServiceLayer.MAX_DURATION_MINUTES} minutes"
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
        if price < ServiceServiceLayer.MIN_SERVICE_PRICE:
            raise ValidationError(
                detail=f"Service price cannot be less than ${ServiceServiceLayer.MIN_SERVICE_PRICE}"
            )

        if price > ServiceServiceLayer.MAX_SERVICE_PRICE:
            raise ValidationError(
                detail=f"Service price cannot exceed ${ServiceServiceLayer.MAX_SERVICE_PRICE}"
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

    @staticmethod
    def can_deactivate_service(service):
        """Check if service can be deactivated"""
        # Check if service has active specialist relationships
        active_relationships = SpecialistService.objects.filter(
            service=service, is_available=True
        ).count()

        if active_relationships > 0:
            # Check if specialists have upcoming appointments with this service
            upcoming_appointments = Appointment.objects.filter(
                specialist__services__service=service,
                status__in=["scheduled", "confirmed"],
                appointment_date__gte=timezone.now(),
            ).count()

            if upcoming_appointments > 0:
                raise BusinessRuleError(
                    detail=f"Cannot deactivate service with {upcoming_appointments} upcoming appointment(s)"
                )

        return True

    @staticmethod
    def can_delete_service(service):
        """Check if service can be deleted"""
        # Services should rarely be deleted; use deactivation instead
        # Check if service has any historical data

        # Check for any appointments that used this service
        appointment_count = Appointment.objects.filter(
            # Assuming appointments have a service field
            # If not, you'd need to check through specialist services
        ).count()

        if appointment_count > 0:
            raise BusinessRuleError(
                detail="Cannot delete service with historical appointment data. Use deactivation instead."
            )

        return True

    @classmethod
    @transaction.atomic
    def create_service(cls, **validated_data):
        """Create a new service with business logic validation"""

        # Extract and validate data
        name = validated_data.get("name")
        category = validated_data.get("category")
        duration_minutes = validated_data.get("duration_minutes")
        base_price = validated_data.get("base_price")

        # Apply business logic validation
        name = cls.validate_service_name(name)
        category = cls.validate_service_category(category)
        duration_minutes = cls.validate_service_duration(duration_minutes)
        base_price = cls.validate_service_price(base_price)

        # Check for uniqueness within category
        if Service.objects.filter(name=name, category=category).exists():
            raise ConflictError(
                detail=f"Service with name '{name}' already exists in category '{category}'"
            )

        # Create service
        service = Service.objects.create(
            name=name,
            category=category,
            duration_minutes=duration_minutes,
            base_price=base_price,
            description=validated_data.get("description", ""),
            is_active=True,
        )

        logger.info(f"Service created: {service.id} - {service.name}")

        # Log creation (placeholder)
        # ServiceAuditService.log_creation(service)

        return service

    @classmethod
    @transaction.atomic
    def update_service(cls, service, **validated_data):
        """Update service with business logic validation"""

        # Track changes for audit
        changes = {}

        # Check if name or category is being changed
        if "name" in validated_data or "category" in validated_data:
            new_name = validated_data.get("name", service.name)
            new_category = validated_data.get("category", service.category)

            # Validate uniqueness if name or category changed
            if new_name != service.name or new_category != service.category:
                if (
                    Service.objects.filter(name=new_name, category=new_category)
                    .exclude(id=service.id)
                    .exists()
                ):
                    raise ConflictError(
                        detail=f"Service with name '{new_name}' already exists in category '{new_category}'"
                    )

            if new_name != service.name:
                new_name = cls.validate_service_name(new_name)
                validated_data["name"] = new_name
                changes["name"] = {"old": service.name, "new": new_name}

            if new_category != service.category:
                new_category = cls.validate_service_category(new_category)
                validated_data["category"] = new_category
                changes["category"] = {"old": service.category, "new": new_category}

        # Validate duration if being updated
        if "duration_minutes" in validated_data:
            new_duration = cls.validate_service_duration(
                validated_data["duration_minutes"]
            )
            if new_duration != service.duration_minutes:
                validated_data["duration_minutes"] = new_duration
                changes["duration_minutes"] = {
                    "old": service.duration_minutes,
                    "new": new_duration,
                }

        # Validate price if being updated
        if "base_price" in validated_data:
            new_price = cls.validate_service_price(validated_data["base_price"])
            if new_price != service.base_price:
                validated_data["base_price"] = new_price
                changes["base_price"] = {"old": service.base_price, "new": new_price}

                # Update specialist service prices if they don't have overrides
                SpecialistService.objects.filter(
                    service=service, price_override__isnull=True
                ).update(
                    is_available=False
                )  # Temporarily disable until reviewed

        # Update service
        for field, value in validated_data.items():
            setattr(service, field, value)

        service.save()
        service.refresh_from_db()

        logger.info(f"Service updated: {service.id} - {service.name}")

        # Log changes if any
        if changes:
            # ServiceAuditService.log_update(service, changes)
            pass

        return service

    @classmethod
    @transaction.atomic
    def deactivate_service(cls, service, deactivated_by=None):
        """Deactivate service (soft delete)"""

        # Check if service can be deactivated
        cls.can_deactivate_service(service)

        # Store old status
        old_status = service.is_active

        # Deactivate service
        service.is_active = False
        service.save()

        # Also deactivate all specialist-service relationships
        SpecialistService.objects.filter(service=service).update(is_available=False)

        logger.info(
            f"Service deactivated: {service.id} - {service.name}. Deactivated by: {deactivated_by}"
        )

        return service

    @classmethod
    @transaction.atomic
    def reactivate_service(cls, service, reactivated_by=None):
        """Reactivate a deactivated service"""

        # Reactivate service
        service.is_active = True
        service.save()

        # Note: Specialist-service relationships remain deactivated
        # They need to be manually reactivated by specialists

        logger.info(f"Service reactivated: {service.id} - {service.name}")

        return service

    @classmethod
    def get_services_by_category(cls, category=None, active_only=True):
        """Get services filtered by category and active status"""
        queryset = Service.objects.all()

        if active_only:
            queryset = queryset.filter(is_active=True)

        if category:
            category = cls.validate_service_category(category)
            queryset = queryset.filter(category=category)

        # Add related data for better performance
        queryset = queryset.prefetch_related("specialists")

        return list(queryset.order_by("name"))

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
                ),
                appointment_count=Count(
                    "appointments",  # Assuming relationship through specialist->appointment
                    filter=Q(
                        appointments__status="completed",
                        appointments__created_at__gte=now - timedelta(days=30),
                    ),
                ),
            )
            .order_by("-specialist_count", "-appointment_count")[:10]
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
                    "appointment_count": service.appointment_count,
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

    @classmethod
    def add_service_to_specialist(
        cls, service, specialist, price_override=None, added_by=None
    ):
        """Add service to specialist's offerings with business logic"""

        # Check if service is active
        if not service.is_active:
            raise BusinessRuleError(detail="Cannot add inactive service to specialist")

        # Check if specialist is active and accepting patients
        if not specialist.is_active:
            raise BusinessRuleError(detail="Cannot add service to inactive specialist")

        # Check if specialist already offers this service
        if SpecialistService.objects.filter(
            specialist=specialist, service=service
        ).exists():
            raise ConflictError(detail="Specialist already offers this service")

        # Validate price override if provided
        if price_override is not None:
            if price_override < 0:
                raise ValidationError(detail="Price override cannot be negative")

            # Price override should be reasonable
            if price_override > service.base_price * 3:
                raise ValidationError(
                    detail="Price override cannot exceed 3 times the base price"
                )

            # Price override should not be too low
            if price_override < service.base_price * 0.5:
                raise ValidationError(
                    detail="Price override cannot be less than 50% of base price"
                )

        # Check if specialist has reached maximum services (if applicable)
        max_services = getattr(specialist, "max_services", 50)  # Default limit
        current_services = SpecialistService.objects.filter(
            specialist=specialist, is_available=True
        ).count()

        if current_services >= max_services:
            raise BusinessRuleError(
                detail=f"Specialist has reached maximum service limit ({max_services})"
            )

        # Create specialist-service relationship
        specialist_service = SpecialistService.objects.create(
            specialist=specialist,
            service=service,
            price_override=price_override,
            is_available=True,
        )

        logger.info(f"Service added to specialist: {service.id} -> {specialist.id}")

        # Log addition (placeholder)
        # ServiceAuditService.log_specialist_addition(specialist_service, added_by)

        return specialist_service

    @classmethod
    def remove_service_from_specialist(cls, specialist_service, removed_by=None):
        """Remove service from specialist's offerings"""

        # Check if specialist has upcoming appointments for this service
        upcoming_appointments = Appointment.objects.filter(
            specialist=specialist_service.specialist,
            # Assuming appointments track service
            # created_at__gte=timezone.now() - timedelta(days=7)  # Last 7 days
        ).count()

        if upcoming_appointments > 0:
            # Instead of removing, just mark as unavailable
            specialist_service.is_available = False
            specialist_service.save()

            logger.info(
                f"Service marked unavailable for specialist: {specialist_service.id}"
            )
        else:
            # Delete the relationship
            specialist_service.delete()
            logger.info(f"Service removed from specialist: {specialist_service.id}")

        # Log removal (placeholder)
        # ServiceAuditService.log_specialist_removal(specialist_service, removed_by)

        return True

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

            if new_price_override < service.base_price * 0.5:
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
