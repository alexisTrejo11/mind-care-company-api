import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from django.core.exceptions import ValidationError as DjangoValidationError

from core.exceptions.base_exceptions import (
    ValidationError,
    NotFoundError,
    ConflictError,
    BusinessRuleError,
)

from ..models import Appointment
from apps.specialists.models import Specialist
from apps.users.models import User

logger = logging.getLogger(__name__)


class AppointmentService:
    """Main service for appointment operations"""

    @staticmethod
    @transaction.atomic
    def create_appointment(
        patient_id: str,
        specialist_id: int,
        appointment_date: datetime,
        appointment_type: str,
        duration_minutes: int,
        **kwargs,
    ) -> Appointment:
        """
        Create a new appointment with validation
        """
        try:
            # Validate participants
            patient = User.objects.get(user_id=patient_id, is_active=True)
            specialist = Specialist.objects.get(id=specialist_id)

            # Validate patient is actually a patient
            if patient.user_type != "patient":
                raise BusinessRuleError(
                    detail="Only patients can schedule appointments",
                    code="invalid_user_type",
                )

            # Validate specialist availability
            if not specialist.is_accepting_new_patients:
                raise BusinessRuleError(
                    detail="Specialist is not accepting new patients",
                    code="specialist_not_accepting",
                )

            # Calculate start and end times
            start_time = appointment_date
            end_time = appointment_date + timedelta(minutes=duration_minutes)

            # Check for scheduling conflicts
            conflict = Appointment.objects.filter(
                Q(specialist=specialist) | Q(patient=patient),
                start_time__lt=end_time,
                end_time__gt=start_time,
                status__in=["scheduled", "confirmed", "in_progress"],
            ).exists()

            if conflict:
                raise ConflictError(
                    detail="Time slot is not available", code="scheduling_conflict"
                )

            # Create appointment
            appointment = Appointment.objects.create(
                patient=patient,
                specialist=specialist,
                appointment_type=appointment_type,
                appointment_date=appointment_date.date(),
                start_time=start_time,
                end_time=end_time,
                duration_minutes=duration_minutes,
                **kwargs,
            )

            logger.info(
                f"Appointment created: {appointment.id} - "
                f"Patient: {patient.email}, Specialist: {specialist.user.email}"
            )

            return appointment

        except User.DoesNotExist:
            raise NotFoundError(detail="Patient not found or inactive")
        except Specialist.DoesNotExist:
            raise NotFoundError(detail="Specialist not found")
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e))

    @staticmethod
    @transaction.atomic
    def update_appointment(appointment_id: int, **update_data) -> Appointment:
        """
        Update appointment information
        """
        try:
            appointment = Appointment.objects.get(id=appointment_id)

            # Check if appointment can be modified
            if appointment.status in ["completed", "cancelled", "no_show"]:
                raise BusinessRuleError(
                    detail=f"Cannot modify appointment with status: {appointment.status}",
                    code="appointment_locked",
                )

            # Handle status transitions
            if "status" in update_data:
                new_status = update_data["status"]
                if new_status != appointment.status:
                    # Validate status transition
                    from ..validators import validate_status_transition

                    try:
                        validate_status_transition(appointment.status, new_status)
                    except DjangoValidationError as e:
                        raise ValidationError(detail=str(e))

                    # Special handling for cancellation
                    if new_status == "cancelled":
                        from ..validators import validate_cancellation_time

                        try:
                            validate_cancellation_time(appointment.start_time)
                        except DjangoValidationError as e:
                            raise ValidationError(detail=str(e))

            # Update fields
            for field, value in update_data.items():
                setattr(appointment, field, value)

            appointment.full_clean()
            appointment.save()

            logger.info(f"Appointment updated: {appointment.id}")

            return appointment

        except Appointment.DoesNotExist:
            raise NotFoundError(detail="Appointment not found")
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e))

    @staticmethod
    @transaction.atomic
    def reschedule_appointment(
        appointment_id: int,
        new_appointment_date: datetime,
        new_duration_minutes: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> Appointment:
        """
        Reschedule an existing appointment
        """
        try:
            appointment = Appointment.objects.select_related(
                "patient", "specialist"
            ).get(id=appointment_id)

            # Validate rescheduling is allowed
            if appointment.status in ["completed", "cancelled", "no_show"]:
                raise BusinessRuleError(
                    detail=f"Cannot reschedule appointment with status: {appointment.status}",
                    code="appointment_locked",
                )

            # Use existing duration if not specified
            duration = new_duration_minutes or appointment.duration_minutes

            # Calculate new times
            new_start_time = new_appointment_date
            new_end_time = new_appointment_date + timedelta(minutes=duration)

            # Check for conflicts with new time
            conflict = (
                Appointment.objects.filter(
                    Q(specialist=appointment.specialist)
                    | Q(patient=appointment.patient),
                    start_time__lt=new_end_time,
                    end_time__gt=new_start_time,
                    status__in=["scheduled", "confirmed", "in_progress"],
                )
                .exclude(id=appointment_id)
                .exists()
            )

            if conflict:
                raise ConflictError(
                    detail="New time slot is not available",
                    code="rescheduling_conflict",
                )

            # Update appointment
            appointment.appointment_date = new_appointment_date.date()
            appointment.start_time = new_start_time
            appointment.end_time = new_end_time
            appointment.duration_minutes = duration

            if reason:
                appointment.notes = f"{appointment.notes}\n\nRescheduled: {reason}"

            appointment.save()

            logger.info(f"Appointment rescheduled: {appointment.id}")

            return appointment

        except Appointment.DoesNotExist:
            raise NotFoundError(detail="Appointment not found")
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e))

    @staticmethod
    def get_appointment_details(appointment_id: int) -> Dict[str, Any]:
        """
        Get detailed appointment information
        """
        try:
            appointment = Appointment.objects.select_related(
                "patient", "specialist", "specialist__user"
            ).get(id=appointment_id)

            # Calculate time until appointment
            now = timezone.now()
            time_until = (
                appointment.start_time - now if appointment.start_time > now else None
            )

            # Prepare response data
            data = {
                "appointment": appointment,
                "metadata": {
                    "is_upcoming": appointment.start_time > now,
                    "is_past": appointment.end_time < now,
                    "is_in_progress": (
                        appointment.start_time <= now <= appointment.end_time
                        and appointment.status == "in_progress"
                    ),
                    "time_until": time_until,
                    "can_cancel": (
                        appointment.status in ["scheduled", "confirmed"]
                        and (appointment.start_time - now) > timedelta(hours=1)
                    ),
                    "can_reschedule": (
                        appointment.status in ["scheduled", "confirmed"]
                        and (appointment.start_time - now) > timedelta(hours=24)
                    ),
                },
            }

            return data

        except Appointment.DoesNotExist:
            raise NotFoundError(detail="Appointment not found")

    @staticmethod
    def search_appointments(
        filters: Dict[str, Any], user: User, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Appointment], Dict[str, Any]]:
        """
        Search appointments with filters
        """
        try:
            # Base queryset with related data
            queryset = Appointment.objects.select_related(
                "patient", "specialist", "specialist__user"
            )

            # Apply role-based filtering
            if user.user_type == "patient":
                queryset = queryset.filter(patient=user)
            elif user.user_type == "specialist":
                if hasattr(user, "specialist_profile"):
                    queryset = queryset.filter(specialist=user.specialist_profile)
            # Admin and staff can see all

            # Apply filters
            if status := filters.get("status"):
                queryset = queryset.filter(status=status)

            if appointment_type := filters.get("appointment_type"):
                queryset = queryset.filter(appointment_type=appointment_type)

            if specialist_id := filters.get("specialist_id"):
                queryset = queryset.filter(specialist_id=specialist_id)

            if patient_id := filters.get("patient_id"):
                queryset = queryset.filter(patient__user_id=patient_id)

            # Date range filtering
            if start_date := filters.get("start_date"):
                queryset = queryset.filter(appointment_date__gte=start_date)

            if end_date := filters.get("end_date"):
                queryset = queryset.filter(appointment_date__lte=end_date)

            # Upcoming vs past filtering
            now = timezone.now()
            if filters.get("is_upcoming"):
                queryset = queryset.filter(start_time__gt=now)
            elif filters.get("is_past"):
                queryset = queryset.filter(end_time__lt=now)

            # Search by text
            if search_query := filters.get("search"):
                queryset = queryset.filter(
                    Q(patient__first_name__icontains=search_query)
                    | Q(patient__last_name__icontains=search_query)
                    | Q(specialist__user__first_name__icontains=search_query)
                    | Q(specialist__user__last_name__icontains=search_query)
                    | Q(notes__icontains=search_query)
                    | Q(symptoms__icontains=search_query)
                )

            # Ordering
            ordering = filters.get("ordering", "-appointment_date")
            queryset = queryset.order_by(ordering, "start_time")

            # Pagination
            total = queryset.count()
            start = (page - 1) * page_size
            end = start + page_size

            appointments = queryset[start:end]

            # Pagination metadata
            pagination = {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
                "has_next": end < total,
                "has_previous": page > 1,
            }

            return list(appointments), pagination

        except Exception as e:
            logger.error(f"Error searching appointments: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def get_appointment_statistics(
        period: str = "month", specialist_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get appointment statistics for a period
        """
        try:
            now = timezone.now()

            # Define period ranges
            if period == "today":
                start_date = now.date()
                end_date = now.date() + timedelta(days=1)
            elif period == "week":
                start_date = now.date() - timedelta(days=7)
                end_date = now.date()
            elif period == "month":
                start_date = now.date() - timedelta(days=30)
                end_date = now.date()
            elif period == "quarter":
                start_date = now.date() - timedelta(days=90)
                end_date = now.date()
            elif period == "year":
                start_date = now.date() - timedelta(days=365)
                end_date = now.date()
            else:
                start_date = now.date() - timedelta(days=30)
                end_date = now.date()

            # Base queryset
            queryset = Appointment.objects.filter(
                appointment_date__gte=start_date, appointment_date__lt=end_date
            )

            if specialist_id:
                queryset = queryset.filter(specialist_id=specialist_id)

            # Calculate statistics
            total_appointments = queryset.count()

            status_counts = (
                queryset.values("status").annotate(count=Count("id")).order_by("status")
            )

            type_counts = (
                queryset.values("appointment_type")
                .annotate(count=Count("id"))
                .order_by("appointment_type")
            )

            # Average duration
            avg_duration = (
                queryset.aggregate(avg_duration=Avg("duration_minutes"))["avg_duration"]
                or 0
            )

            # Busiest days
            busiest_days = (
                queryset.values("appointment_date")
                .annotate(count=Count("id"))
                .order_by("-count")[:5]
            )

            # No-show rate
            no_show_count = queryset.filter(status="no_show").count()
            no_show_rate = (
                (no_show_count / total_appointments * 100)
                if total_appointments > 0
                else 0
            )

            # Cancellation rate
            cancelled_count = queryset.filter(status="cancelled").count()
            cancellation_rate = (
                (cancelled_count / total_appointments * 100)
                if total_appointments > 0
                else 0
            )

            return {
                "period": period,
                "date_range": {
                    "start_date": start_date,
                    "end_date": end_date,
                },
                "total_appointments": total_appointments,
                "status_distribution": list(status_counts),
                "type_distribution": list(type_counts),
                "avg_duration_minutes": round(avg_duration, 1),
                "busiest_days": list(busiest_days),
                "no_show_rate": round(no_show_rate, 2),
                "cancellation_rate": round(cancellation_rate, 2),
                "completion_rate": round(100 - no_show_rate - cancellation_rate, 2),
            }

        except Exception as e:
            logger.error(
                f"Error getting appointment statistics: {str(e)}", exc_info=True
            )
            raise
