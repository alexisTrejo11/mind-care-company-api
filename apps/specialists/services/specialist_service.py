from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Avg, Sum, F, Value
from django.db.models.functions import Concat, TruncDate
from decimal import Decimal
import decimal

from ..models import Specialist, Service, SpecialistService, Availability
from apps.appointments.models import Appointment
from apps.core.exceptions.base_exceptions import (
    BusinessRuleError,
    ValidationError,
    NotFoundError,
    AuthorizationError,
)


class SpecialistServiceLayer:
    """Service layer for specialist business logic"""

    MIN_YEARS_EXPERIENCE = 0
    # (reasonable limit)
    MAX_YEARS_EXPERIENCE = 60
    MIN_CONSULTATION_FEE = Decimal("10.00")
    MAX_CONSULTATION_FEE = Decimal("1000.00")
    MIN_RATING = Decimal("0.00")
    MAX_RATING = Decimal("5.00")

    @staticmethod
    def validate_license_number(license_number, exclude_specialist_id=None):
        """Validate license number format and uniqueness"""
        if (
            not license_number
            or len(license_number.strip()) < 3
            or len(license_number.strip()) > 30
        ):
            raise ValidationError(
                detail="License number must be between 3 and 30 characters long"
            )

        # Check uniqueness
        query = Specialist.objects.filter(license_number=license_number)
        if exclude_specialist_id:
            query = query.exclude(id=exclude_specialist_id)

        if query.exists():
            raise ValidationError(detail="License number already registered")

        return license_number.strip()

    @staticmethod
    def validate_years_experience(years):
        """Validate years of experience"""
        if years < SpecialistServiceLayer.MIN_YEARS_EXPERIENCE:
            raise ValidationError(
                detail=f"Years experience cannot be less than {SpecialistServiceLayer.MIN_YEARS_EXPERIENCE}"
            )

        if years > SpecialistServiceLayer.MAX_YEARS_EXPERIENCE:
            raise ValidationError(
                detail=f"Years experience cannot exceed {SpecialistServiceLayer.MAX_YEARS_EXPERIENCE}"
            )

        return years

    @staticmethod
    def validate_consultation_fee(fee):
        """Validate consultation fee"""
        if fee < SpecialistServiceLayer.MIN_CONSULTATION_FEE:
            raise ValidationError(
                detail=f"Consultation fee cannot be less than ${SpecialistServiceLayer.MIN_CONSULTATION_FEE}"
            )

        if fee > SpecialistServiceLayer.MAX_CONSULTATION_FEE:
            raise ValidationError(
                detail=f"Consultation fee cannot exceed ${SpecialistServiceLayer.MAX_CONSULTATION_FEE}"
            )

        return fee

    @staticmethod
    def validate_rating(rating):
        """Validate specialist rating"""
        if rating < SpecialistServiceLayer.MIN_RATING:
            raise ValidationError(
                detail=f"Rating cannot be less than {SpecialistServiceLayer.MIN_RATING}"
            )

        if rating > SpecialistServiceLayer.MAX_RATING:
            raise ValidationError(
                detail=f"Rating cannot exceed {SpecialistServiceLayer.MAX_RATING}"
            )

        return rating

    @staticmethod
    def calculate_rating(specialist):
        """Calculate average rating from reviews (placeholder)"""
        # TODO: Implement actual review fetching and averaging
        return specialist.rating

    @staticmethod
    def can_handle_appointment_type(specialist, appointment_type):
        """Check if specialist can handle specific appointment type"""
        # Base implementation - all specialists can handle all types
        # This can be extended with more complex logic

        # Example: Some specialists might not handle emergency appointments
        if appointment_type == "emergency":
            # Check if specialist is trained for emergencies
            # This would check qualifications, training, etc.
            return "emergency_trained" in specialist.qualifications.lower()

        return True

    @staticmethod
    def validate_specialist_creation(user_data, specialist_data):
        """Validate specialist creation data"""
        # Validate user exists and is not already a specialist
        from django.contrib.auth import get_user_model

        User = get_user_model()

        user_id = user_data.get("user_id")
        try:
            user = User.objects.get(id=user_id)
            if hasattr(user, "specialist_profile"):
                raise ValidationError(detail="User already has a specialist profile")
        except User.DoesNotExist:
            raise NotFoundError(detail="User not found")

        # Validate specialist data
        license_number = specialist_data.get("license_number")
        SpecialistServiceLayer.validate_license_number(license_number)

        years_experience = specialist_data.get("years_experience", 0)
        SpecialistServiceLayer.validate_years_experience(years_experience)

        consultation_fee = specialist_data.get("consultation_fee", Decimal("0.00"))
        SpecialistServiceLayer.validate_consultation_fee(consultation_fee)

        rating = specialist_data.get("rating", Decimal("0.00"))
        SpecialistServiceLayer.validate_rating(rating)

        return user, specialist_data

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
        cls.validate_license_number(license_number)

        years_experience = validated_data.get("years_experience", 0)
        cls.validate_years_experience(years_experience)

        consultation_fee = validated_data.get("consultation_fee", Decimal("0.00"))
        cls.validate_consultation_fee(consultation_fee)

        rating = validated_data.get("rating", Decimal("0.00"))
        cls.validate_rating(rating)

        # Create specialist
        specialist = Specialist.objects.create(user=user, **validated_data)

        # Create default availability (placeholder)
        # cls.create_default_availability(specialist)

        return specialist

    @classmethod
    @transaction.atomic
    def update_specialist(cls, specialist_id, **validated_data):
        """Update specialist with business logic validation"""
        try:
            specialist = Specialist.objects.select_for_update().get(id=specialist_id)
        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")

        # Validate license number if being updated
        if "license_number" in validated_data:
            validated_data["license_number"] = cls.validate_license_number(
                validated_data["license_number"], exclude_specialist_id=specialist_id
            )

        # Validate years_experience if being updated
        if "years_experience" in validated_data:
            validated_data["years_experience"] = cls.validate_years_experience(
                validated_data["years_experience"]
            )

        # Validate consultation_fee if being updated
        if "consultation_fee" in validated_data:
            validated_data["consultation_fee"] = cls.validate_consultation_fee(
                validated_data["consultation_fee"]
            )

        # Validate rating if being updated
        if "rating" in validated_data:
            validated_data["rating"] = cls.validate_rating(validated_data["rating"])

        # Update specialist
        for field, value in validated_data.items():
            setattr(specialist, field, value)

        specialist.save()

        return specialist

    @classmethod
    @transaction.atomic
    def delete_specialist(cls, specialist_id, deleted_by):
        """Delete specialist (admin only with audit trail)"""
        try:
            specialist = Specialist.objects.select_for_update().get(id=specialist_id)
        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")

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

        # Log deactivation (placeholder)
        # SpecialistAuditService.log_deletion(specialist, deleted_by)

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
    def get_specialist_detail(cls, specialist_id):
        """Get specialist details with statistics"""
        try:
            specialist = Specialist.objects.select_related("user").get(id=specialist_id)
        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")

        # Calculate statistics
        stats = cls.get_specialist_statistics(specialist_id)

        return {"specialist": specialist, "stats": stats}

    @classmethod
    def get_specialist_statistics(cls, specialist_id):
        """Get statistics for a specialist"""
        try:
            specialist = Specialist.objects.get(id=specialist_id)
        except Specialist.DoesNotExist:
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
            "availability_percentage": cls.calculate_availability_percentage(
                specialist_id
            ),
        }

    @staticmethod
    def calculate_availability_percentage(specialist_id):
        """Calculate specialist availability percentage"""
        # Get total available hours per week
        availabilities = Availability.objects.filter(
            specialist_id=specialist_id,
            is_recurring=True,
            valid_until__gte=timezone.now().date(),
        )

        if not availabilities.exists():
            return 0.0

        total_hours = 0
        for avail in availabilities:
            # Calculate hours per slot
            hours = (avail.end_time.hour - avail.start_time.hour) + (
                avail.end_time.minute - avail.start_time.minute
            ) / 60
            total_hours += hours

        # Maximum possible hours (8 hours/day * 5 days)
        max_hours = 40

        # Calculate percentage
        percentage = min((total_hours / max_hours) * 100, 100)

        return round(percentage, 2)

    @classmethod
    def add_service_to_specialist(cls, specialist_id, service_id, price_override=None):
        """Add service to specialist's offerings"""
        try:
            specialist = Specialist.objects.get(id=specialist_id)
            service = Service.objects.get(id=service_id, is_active=True)
        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")
        except Service.DoesNotExist:
            raise NotFoundError(detail="Service not found or inactive")

        # Check if service already exists
        if SpecialistService.objects.filter(
            specialist=specialist, service=service
        ).exists():
            raise ValidationError(detail="Specialist already offers this service")

        # Validate price override if provided
        if price_override is not None:
            # Convert to Decimal if it's a string
            if isinstance(price_override, str):
                try:
                    price_override = Decimal(price_override)
                except (ValueError, decimal.InvalidOperation):
                    raise ValidationError(detail="Invalid price override format")

            if price_override < 0:
                raise ValidationError(detail="Price override cannot be negative")

            # Price override should be reasonable (not more than 3x base price)
            if price_override > service.base_price * 3:
                raise ValidationError(
                    detail="Price override cannot exceed 3 times the base price"
                )

        # Create specialist-service relationship
        specialist_service = SpecialistService.objects.create(
            specialist=specialist,
            service=service,
            price_override=price_override,
            is_available=True,
        )

        return specialist_service

    @classmethod
    def remove_service_from_specialist(cls, specialist_id, service_id):
        """Remove service from specialist's offerings"""
        try:
            specialist_service = SpecialistService.objects.get(
                specialist_id=specialist_id, service_id=service_id
            )
        except SpecialistService.DoesNotExist:
            raise NotFoundError(detail="Service not found in specialist's offerings")

        # Instead of deleting, mark as unavailable
        specialist_service.is_available = False
        specialist_service.save()

        return specialist_service

    @classmethod
    def update_service_price(cls, specialist_id, service_id, price_override):
        """Update price override for specialist's service"""
        try:
            specialist_service = SpecialistService.objects.get(
                specialist_id=specialist_id, service_id=service_id
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

        return specialist_service

    @classmethod
    def get_specialists_by_specialization(cls):
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

    @classmethod
    def get_specialist_availability_slots(cls, specialist_id, date):
        """Get available time slots for a specialist on a specific date"""
        try:
            specialist = Specialist.objects.get(id=specialist_id)
        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")

        # Get specialist's availability for the day of week
        target_date = timezone.datetime.strptime(date, "%Y-%m-%d").date()
        day_of_week = target_date.weekday()  # Monday=0, Sunday=6

        availabilities = Availability.objects.filter(
            specialist=specialist,
            day_of_week=day_of_week,
            is_recurring=True,
            valid_from__lte=target_date,
            valid_until__gte=target_date,
        )

        # Get existing appointments for the day
        appointments = Appointment.objects.filter(
            specialist=specialist,
            appointment_date__date=target_date,
            status__in=["scheduled", "confirmed"],
        )

        # Default appointment duration (can be customized per specialist)
        duration_minutes = 90

        # Generate available slots
        available_slots = []
        for availability in availabilities:
            current_time = availability.start_time
            end_time = availability.end_time

            while current_time < end_time:
                # Calculate slot end time by adding duration to current time
                slot_end_datetime = timezone.datetime.combine(
                    target_date, current_time
                ) + timedelta(minutes=duration_minutes)
                slot_end = slot_end_datetime.time()

                # Check if slot would exceed availability end time
                if slot_end > end_time:
                    break

                # Convert current slot to datetime for comparison with appointments
                slot_start_datetime = timezone.datetime.combine(
                    target_date, current_time
                )

                # Check if slot is available (no overlapping appointment)
                slot_available = True
                for appointment in appointments:
                    # Compare datetime objects
                    if (
                        slot_start_datetime < appointment.end_time
                        and slot_end_datetime > appointment.start_time
                    ):
                        slot_available = False
                        break

                if slot_available:
                    available_slots.append(
                        {
                            "start_time": current_time.strftime("%H:%M"),
                            "end_time": slot_end.strftime("%H:%M"),
                            "duration_minutes": duration_minutes,
                        }
                    )

                # Move to next slot
                current_time = slot_end

        return {
            "specialist_id": specialist_id,
            "date": date,
            "day_of_week": dict(Availability.DAY_CHOICES)[day_of_week],
            "available_slots": available_slots,
            "total_slots": len(available_slots),
        }
