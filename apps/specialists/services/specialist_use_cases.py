import logging
from typing import List, Dict
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from datetime import timedelta

from ..models import Specialist, Service, SpecialistService
from apps.appointments.models import Appointment
from apps.core.exceptions.base_exceptions import (
    BusinessRuleError,
    ConflictError,
    ValidationError,
    NotFoundError,
)
from .specialist_validators import SpecialistValidator
from .specialist_availability import SpecialistAvailabilityUseCases

logger = logging.getLogger(__name__)


class SpecialistsUseCases:
    """Service uses cases for specialist business logic"""

    @staticmethod
    def get_base_queryset_for_list():
        """
        Base queryset optimized for public lists.
        Includes fixed business filters (active) and optimizations.
        DRF will apply dynamic filters and ordering on this queryset.
        """
        return Specialist.objects.select_related("user").filter(
            user__is_active=True, is_active=True
        )

    @staticmethod
    def get_specialist_services(specialist: Specialist) -> List["SpecialistService"]:
        """
        Returns active services for a specialist with prefetch.
        """
        if not specialist or not isinstance(specialist, Specialist):
            raise ValidationError(detail="Invalid specialist provided")

        return (
            specialist.services.filter(is_available=True)
            .select_related("service")
            .order_by("service__name")
        )

    @staticmethod
    def calculate_rating(specialist):
        """Calculate average rating from reviews (placeholder)"""
        # TODO: Implement actual review fetching and averaging
        return specialist.rating

    @classmethod
    @transaction.atomic
    def create_specialist(cls, **validated_data):
        """Create a new specialist with business logic validation"""

        # Extract user and specialist data
        user = validated_data.pop("user")
        if not user:
            raise ValidationError(detail="User data is required to create specialist")

        # Apply business logic validation
        license_number = validated_data.get("license_number")
        cls._validate_license_number(license_number)

        years_experience = validated_data.get("years_experience", 0)
        cls._validate_years_experience(years_experience)

        consultation_fee = validated_data.get("consultation_fee", Decimal("0.00"))
        cls._validate_consultation_fee(consultation_fee)

        rating = validated_data.get("rating", Decimal("0.00"))
        cls._validate_rating(rating)

        # Create specialist
        specialist = Specialist.objects.create(user=user, **validated_data)

        logger.info(
            f"Specialist created: {specialist.id} - {specialist.user.get_full_name()}"
        )

        return specialist

    @classmethod
    @transaction.atomic
    def update_specialist(cls, specialist, **validated_data):
        """Update specialist with business logic validation"""
        if not specialist:
            raise NotFoundError(detail="Specialist not found")

        # Validate license number if being updated
        if "license_number" in validated_data:
            validated_data["license_number"] = (
                SpecialistValidator.validate_license_number(
                    validated_data["license_number"],
                    exclude_specialist_id=specialist.id,
                )
            )

        # Validate years_experience if being updated
        if "years_experience" in validated_data:
            validated_data["years_experience"] = (
                SpecialistValidator.validate_years_experience(
                    validated_data["years_experience"]
                )
            )

        # Validate consultation_fee if being updated
        if "consultation_fee" in validated_data:
            validated_data["consultation_fee"] = (
                SpecialistValidator.validate_consultation_fee(
                    validated_data["consultation_fee"]
                )
            )

        # Validate rating if being updated
        if "rating" in validated_data:
            validated_data["rating"] = SpecialistValidator.validate_rating(
                validated_data["rating"]
            )

        # Update specialist
        for field, value in validated_data.items():
            setattr(specialist, field, value)

        specialist.save()

        logger.info(
            f"Specialist updated: {specialist.id} - {specialist.user.get_full_name()}"
        )

        return specialist

    @classmethod
    @transaction.atomic
    def delete_specialist(cls, specialist, deleted_by):
        """Delete specialist (admin only with audit trail)"""

        # Check if specialist has upcoming appointments
        upcoming_appointments = Appointment.objects.filter(
            specialist=specialist,
            status__in=["scheduled", "confirmed"],
            appointment_date__gte=timezone.now(),
        ).count()

        if upcoming_appointments > 0:
            raise BusinessRuleError(
                detail=f"Cannot delete specialist with {upcoming_appointments} upcoming appointment(s)"
            )

        # Instead of deleting, deactivate the specialist
        # This preserves historical data and relationships
        specialist.is_active = False
        specialist.is_accepting_new_patients = False
        specialist.save()

        # Also deactivate all specialist services
        SpecialistService.objects.filter(specialist=specialist).update(
            is_available=False
        )

        logger.info(
            f"Specialist deactivated: {specialist.id} - {specialist.user.get_full_name()}"
        )

        return specialist

    @classmethod
    def search_specialists(cls, filters, page=1, page_size=20):
        """Search specialists with filters and business logic"""
        queryset = Specialist.objects.select_related("user").filter(
            user__is_active=True, is_active=True
        )

        # Apply filters
        specialization = filters.get("specialization")
        if specialization:
            queryset = queryset.filter(specialization=specialization)

        min_rating = filters.get("min_rating")
        if min_rating:
            queryset = queryset.filter(rating__gte=min_rating)

        max_fee = filters.get("max_fee")
        if max_fee:
            queryset = queryset.filter(consultation_fee__lte=max_fee)

        accepting_new_patients = filters.get("accepting_new_patients")
        if accepting_new_patients is not None:
            queryset = queryset.filter(is_accepting_new_patients=accepting_new_patients)

        service_id = filters.get("service_id")
        if service_id:
            queryset = queryset.filter(
                services__service_id=service_id, services__is_available=True
            ).distinct()

        search = filters.get("search")
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(user__email__icontains=search)
                | Q(qualifications__icontains=search)
                | Q(bio__icontains=search)
                | Q(specialization__icontains=search)
            )

        # Apply ordering
        ordering = filters.get("ordering", "-rating")
        queryset = queryset.order_by(ordering)

        # Calculate pagination
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

        return specialists, pagination

    @classmethod
    def get_specialist_detail(cls, specialist):
        """Get specialist details with statistics"""
        if not specialist:
            raise NotFoundError(detail="Specialist not found")

        stats = cls.get_specialist_statistics(specialist)

        return {"specialist": specialist, "stats": stats}

    @classmethod
    def get_specialist_statistics(cls, specialist):
        """Get statistics for a specialist"""
        if not specialist:
            raise NotFoundError(detail="Specialist not found")

        # Appointment statistics
        from apps.appointments.models import Appointment

        total_appointments = Appointment.objects.filter(specialist=specialist).count()

        # Recent appointments (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_appointments = Appointment.objects.filter(
            specialist=specialist, created_at__gte=thirty_days_ago
        ).count()

        # Patient count (unique patients)
        patient_count = (
            Appointment.objects.filter(specialist=specialist)
            .values("patient")
            .distinct()
            .count()
        )

        # Average rating (from reviews - placeholder)
        avg_rating = float(specialist.rating)

        # Today's appointments
        today = timezone.now().date()
        todays_appointments = Appointment.objects.filter(
            specialist=specialist, appointment_date=today
        ).count()

        # Upcoming appointments
        upcoming_appointments = Appointment.objects.filter(
            specialist=specialist,
            status__in=["scheduled", "confirmed"],
            appointment_date__gte=today,
        ).count()

        # Cancellation rate
        cancelled_appointments = Appointment.objects.filter(
            specialist=specialist, status="cancelled"
        ).count()
        cancellation_rate = (
            (cancelled_appointments / total_appointments * 100)
            if total_appointments > 0
            else 0
        )

        # Revenue statistics (placeholder - would integrate with billing)
        # TODO: Calculate actual revenue from Bill model
        total_revenue = Decimal("0.00")
        try:
            from apps.billing.models import Bill

            bills = Bill.objects.filter(
                appointment__specialist=specialist, payment_status="paid"
            )
            total_revenue = bills.aggregate(Sum("total_amount"))[
                "total_amount__sum"
            ] or Decimal("0.00")
        except ImportError:
            pass

        return {
            "total_appointments": total_appointments,
            "recent_appointments": recent_appointments,
            "patient_count": patient_count,
            "avg_rating": avg_rating,
            "todays_appointments": todays_appointments,
            "upcoming_appointments": upcoming_appointments,
            "cancellation_rate": round(cancellation_rate, 2),
            "total_revenue": float(total_revenue),
            "accepting_new_patients": specialist.is_accepting_new_patients,
            "availability_percentage": SpecialistAvailabilityUseCases.calculate_availability_percentage(
                specialist.id
            ),
        }

    @classmethod
    def add_service_to_specialist(cls, specialist, service_id, price_override=None):
        """Add service to specialist's offerings"""
        try:
            service = Service.objects.get(id=service_id, is_active=True)
        except Service.DoesNotExist:
            raise NotFoundError(detail="Service not found or inactive")

        if not specialist.is_active:
            raise BusinessRuleError(detail="Cannot add service to inactive specialist")

        # Check if service already exists
        if SpecialistService.objects.filter(
            specialist=specialist, service=service
        ).exists():
            raise ConflictError(detail="Specialist already offers this service")

        # Validate price override if provided
        if price_override is not None:
            price_override = SpecialistValidator.validate_price_override(
                price_override, service.base_price
            )

        # Create specialist-service relationship
        specialist_service = SpecialistService.objects.create(
            specialist=specialist,
            service=service,
            price_override=price_override,
            is_available=True,
        )

        logger.info(f"Service {service_id} added to specialist {specialist.id}")

        return specialist_service

    @classmethod
    def remove_service_from_specialist(cls, specialist, service_id):
        """Remove service from specialist's offerings"""
        try:
            specialist_service = SpecialistService.objects.get(
                specialist=specialist, service_id=service_id
            )
        except SpecialistService.DoesNotExist:
            raise NotFoundError(detail="Service not found in specialist's offerings")

        # Instead of deleting, mark as unavailable
        specialist_service.is_available = False
        specialist_service.save()

        logger.info(f"Service {service_id} removed from specialist {specialist.id}")

        return specialist_service

    @classmethod
    def update_service_price(cls, specialist, service_id, price_override):
        """Update price override for specialist's service"""
        try:
            specialist_service = SpecialistService.objects.get(
                specialist_id=specialist.id, service_id=service_id
            )
        except SpecialistService.DoesNotExist:
            raise NotFoundError(detail="Service not found in specialist's offerings")

        # Validate price override
        if price_override is not None and price_override < 0:
            raise ValidationError(detail="Price cannot be negative")

        if price_override > specialist_service.service.base_price * 3:
            raise ValidationError(
                detail="Price override cannot exceed 3 times the base price"
            )

        specialist_service.price_override = price_override
        specialist_service.save()

        logger.info(f"Service price updated for specialist {specialist.id}")

        return specialist_service

    @classmethod
    def get_specialists_by_specialization(cls) -> Dict:
        """Get specialists grouped by specialization"""
        # Get all specializations with counts
        specializations = (
            Specialist.objects.filter(is_active=True, is_accepting_new_patients=True)
            .values("specialization")
            .annotate(
                count=Count("id"),
                avg_rating=Avg("rating"),
                avg_fee=Avg("consultation_fee"),
                avg_experience=Avg("years_experience"),
            )
            .order_by("specialization")
        )

        # Get top specialists for each specialization
        result = {}
        for spec in specializations:
            specialization = spec["specialization"]
            specialists = (
                Specialist.objects.filter(
                    specialization=specialization,
                    is_active=True,
                    is_accepting_new_patients=True,
                )
                .select_related("user")
                .order_by("-rating")[:5]
            )

            result[specialization] = {
                "display_name": dict(Specialist.SPECIALIZATION_CHOICES).get(
                    specialization, specialization
                ),
                "count": spec["count"],
                "avg_rating": float(spec["avg_rating"] or 0),
                "avg_fee": float(spec["avg_fee"] or 0),
                "avg_experience": float(spec["avg_experience"] or 0),
                "top_specialists": specialists,
            }

        return result

    @staticmethod
    def _validate_license_number(license_number: str):
        """Wrapper for license number validation"""
        return SpecialistValidator.validate_license_number(license_number)

    @staticmethod
    def _validate_years_experience(years: int):
        """Wrapper for years experience validation"""
        return SpecialistValidator.validate_years_experience(years)

    @staticmethod
    def _validate_consultation_fee(fee: Decimal):
        """Wrapper for consultation fee validation"""
        return SpecialistValidator.validate_consultation_fee(fee)

    @staticmethod
    def _validate_rating(rating):
        """Wrapper for rating validation"""
        return SpecialistValidator.validate_rating(rating)
