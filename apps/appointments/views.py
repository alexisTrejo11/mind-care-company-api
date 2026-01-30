from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.generics import ListAPIView
from datetime import datetime, timedelta

from core.decorators.error_handler import api_error_handler
from core.decorators.permissions import (
    require_permissions,
    user_is_patient,
    user_is_specialist,
    user_is_admin_or_staff,
)
from core.responses.api_response import APIResponse

from .models import Appointment
from .serializers import (
    AppointmentSerializer,
    AppointmentCreateSerializer,
    AppointmentUpdateSerializer,
    AppointmentRescheduleSerializer,
    AppointmentFilterSerializer,
    AppointmentStatsSerializer,
)
from .services import AppointmentService, AvailabilityChecker


class AppointmentListView(APIView):
    """
    GET /api/appointments/
    List and search appointments with filters
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def get(self, request):
        """List appointments with filters"""
        # Validate filter parameters
        filter_serializer = AppointmentFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)

        filters = filter_serializer.validated_data
        page = filters.pop("page", 1)
        page_size = filters.pop("page_size", 20)

        # Get appointments using service
        appointments, pagination = AppointmentService.search_appointments(
            filters=filters, user=request.user, page=page, page_size=page_size
        )

        serializer = AppointmentSerializer(appointments, many=True)

        return APIResponse.success(
            message="Appointments retrieved successfully",
            data=serializer.data,
            pagination=pagination,
        )


class AppointmentCreateView(APIView):
    """
    POST /api/appointments/create/
    Create a new appointment
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_patient, user_is_admin_or_staff])
    def post(self, request):
        """Create new appointment"""
        serializer = AppointmentCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        # Create appointment using service
        appointment = AppointmentService.create_appointment(**serializer.validated_data)

        # Send confirmation notification
        AppointmentNotificationService.send_status_update_notification(
            appointment_id=appointment.id, old_status="", new_status=appointment.status
        )

        return APIResponse.created(
            message="Appointment scheduled successfully",
            data=AppointmentSerializer(appointment).data,
        )


class AppointmentDetailView(APIView):
    """
    GET /api/appointments/<id>/
    Get appointment details
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def get(self, request, appointment_id):
        """Get appointment details"""
        # Check permissions
        appointment = Appointment.objects.get(id=appointment_id)

        if request.user.user_type == "patient":
            if appointment.patient != request.user:
                raise PermissionError("Cannot view another patient's appointment")
        elif request.user.user_type == "specialist":
            if not hasattr(request.user, "specialist_profile"):
                raise PermissionError("User is not a specialist")
            if appointment.specialist != request.user.specialist_profile:
                raise PermissionError("Cannot view another specialist's appointment")
        # Admin and staff can view all

        # Get detailed appointment info
        appointment_data = AppointmentService.get_appointment_details(appointment_id)

        serializer = AppointmentSerializer(appointment_data["appointment"])
        response_data = serializer.data
        response_data["metadata"] = appointment_data["metadata"]

        return APIResponse.success(
            message="Appointment details retrieved", data=response_data
        )


class AppointmentUpdateView(APIView):
    """
    PATCH /api/appointments/<id>/update/
    Update appointment information
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def patch(self, request, appointment_id):
        """Update appointment"""
        # Get appointment and check permissions
        appointment = Appointment.objects.get(id=appointment_id)
        self._check_update_permissions(request.user, appointment)

        serializer = AppointmentUpdateSerializer(
            appointment, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        # Track old status for notification
        old_status = appointment.status

        # Update using service
        appointment = AppointmentService.update_appointment(
            appointment_id=appointment_id, **serializer.validated_data
        )

        # Send status update notification if status changed
        if "status" in serializer.validated_data:
            AppointmentNotificationService.send_status_update_notification(
                appointment_id=appointment_id,
                old_status=old_status,
                new_status=appointment.status,
            )

        return APIResponse.success(
            message="Appointment updated successfully",
            data=AppointmentSerializer(appointment).data,
        )

    def _check_update_permissions(self, user, appointment):
        """Check if user can update this appointment"""
        if user.user_type == "patient":
            if appointment.patient != user:
                raise PermissionError("Cannot update another patient's appointment")
            # Patients can only update notes and symptoms
            allowed_fields = ["notes", "symptoms"]
            if any(field not in allowed_fields for field in self.request.data.keys()):
                raise PermissionError("Patients can only update notes and symptoms")

        elif user.user_type == "specialist":
            if not hasattr(user, "specialist_profile"):
                raise PermissionError("User is not a specialist")
            if appointment.specialist != user.specialist_profile:
                raise PermissionError("Cannot update another specialist's appointment")

        # Admin and staff can update everything


class AppointmentCancelView(APIView):
    """
    POST /api/appointments/<id>/cancel/
    Cancel an appointment
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def post(self, request, appointment_id):
        """Cancel appointment"""
        # Get appointment and check permissions
        appointment = Appointment.objects.get(id=appointment_id)
        self._check_cancel_permissions(request.user, appointment)

        # Track old status
        old_status = appointment.status

        # Update status to cancelled
        appointment = AppointmentService.update_appointment(
            appointment_id=appointment_id, status="cancelled"
        )

        # Send cancellation notification
        AppointmentNotificationService.send_status_update_notification(
            appointment_id=appointment_id, old_status=old_status, new_status="cancelled"
        )

        return APIResponse.success(
            message="Appointment cancelled successfully",
            data=AppointmentSerializer(appointment).data,
        )

    def _check_cancel_permissions(self, user, appointment):
        """Check if user can cancel this appointment"""
        if user.user_type == "patient":
            if appointment.patient != user:
                raise PermissionError("Cannot cancel another patient's appointment")

        elif user.user_type == "specialist":
            if not hasattr(user, "specialist_profile"):
                raise PermissionError("User is not a specialist")
            if appointment.specialist != user.specialist_profile:
                raise PermissionError("Cannot cancel another specialist's appointment")

        # Admin and staff can cancel any appointment


class AppointmentRescheduleView(APIView):
    """
    POST /api/appointments/<id>/reschedule/
    Reschedule an appointment
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def post(self, request, appointment_id):
        """Reschedule appointment"""
        # Get appointment and check permissions
        appointment = Appointment.objects.get(id=appointment_id)
        self._check_reschedule_permissions(request.user, appointment)

        serializer = AppointmentRescheduleSerializer(
            data=request.data, context={"request": request, "appointment": appointment}
        )
        serializer.is_valid(raise_exception=True)

        # Reschedule using service
        appointment = AppointmentService.reschedule_appointment(
            appointment_id=appointment_id, **serializer.validated_data
        )

        # Send rescheduling notification
        AppointmentNotificationService.send_status_update_notification(
            appointment_id=appointment_id,
            old_status="scheduled",  # Treat as status update
            new_status="scheduled",  # Still scheduled, just at new time
        )

        return APIResponse.success(
            message="Appointment rescheduled successfully",
            data=AppointmentSerializer(appointment).data,
        )

    def _check_reschedule_permissions(self, user, appointment):
        """Check if user can reschedule this appointment"""
        if user.user_type == "patient":
            if appointment.patient != user:
                raise PermissionError("Cannot reschedule another patient's appointment")

        elif user.user_type == "specialist":
            if not hasattr(user, "specialist_profile"):
                raise PermissionError("User is not a specialist")
            if appointment.specialist != user.specialist_profile:
                raise PermissionError(
                    "Cannot reschedule another specialist's appointment"
                )

        # Admin and staff can reschedule any appointment


class CheckAvailabilityView(APIView):
    """
    GET /api/appointments/check-availability/
    Check specialist availability for a time slot
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_patient, user_is_admin_or_staff])
    def get(self, request):
        """Check availability"""
        specialist_id = request.query_params.get("specialist_id")
        start_time_str = request.query_params.get("start_time")
        end_time_str = request.query_params.get("end_time")

        if not all([specialist_id, start_time_str, end_time_str]):
            return APIResponse.error(
                message="specialist_id, start_time, and end_time are required",
                code="missing_parameters",
            )

        try:
            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.fromisoformat(end_time_str)

            # Check availability
            is_available = AvailabilityChecker.check_specialist_availability(
                specialist_id=int(specialist_id),
                start_time=start_time,
                end_time=end_time,
            )

            return APIResponse.success(
                message="Availability checked",
                data={
                    "is_available": is_available,
                    "specialist_id": specialist_id,
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )

        except ValueError:
            return APIResponse.error(
                message="Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)",
                code="invalid_date_format",
            )


class AvailableSlotsView(APIView):
    """
    GET /api/appointments/available-slots/
    Get all available time slots for a specialist
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_patient, user_is_admin_or_staff])
    def get(self, request):
        """Get available slots"""
        specialist_id = request.query_params.get("specialist_id")
        date_str = request.query_params.get("date")
        service_duration = int(request.query_params.get("duration", 60))

        if not all([specialist_id, date_str]):
            return APIResponse.error(
                message="specialist_id and date are required", code="missing_parameters"
            )

        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()

            # Get available slots
            slots = AvailabilityChecker.get_available_time_slots(
                specialist_id=int(specialist_id),
                date=date,
                service_duration=service_duration,
            )

            # Format slots for response
            formatted_slots = [
                {
                    "start_time": slot["start_time"].isoformat(),
                    "end_time": slot["end_time"].isoformat(),
                    "duration_minutes": slot["duration_minutes"],
                    "date": date_str,
                }
                for slot in slots
            ]

            return APIResponse.success(
                message="Available slots retrieved",
                data={
                    "specialist_id": specialist_id,
                    "date": date_str,
                    "service_duration": service_duration,
                    "slots": formatted_slots,
                    "total_slots": len(formatted_slots),
                },
            )

        except ValueError:
            return APIResponse.error(
                message="Invalid date format. Use YYYY-MM-DD",
                code="invalid_date_format",
            )


class AppointmentStatsView(APIView):
    """
    GET /api/appointments/stats/
    Get appointment statistics
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_admin_or_staff, user_is_specialist])
    def get(self, request):
        """Get appointment statistics"""
        stats_serializer = AppointmentStatsSerializer(data=request.query_params)
        stats_serializer.is_valid(raise_exception=True)

        # For specialists, only show their own stats
        specialist_id = None
        if request.user.user_type == "specialist":
            if hasattr(request.user, "specialist_profile"):
                specialist_id = request.user.specialist_profile.id

        # Allow filtering by specialist for admins
        if request.user.user_type in ["admin", "staff"]:
            specialist_id = request.query_params.get("specialist_id", specialist_id)

        # Get statistics using service
        stats = AppointmentService.get_appointment_statistics(
            period=stats_serializer.validated_data["period"],
            specialist_id=specialist_id,
        )

        return APIResponse.success(
            message="Appointment statistics retrieved", data=stats
        )


class MyAppointmentsView(APIView):
    """
    GET /api/appointments/me/
    Get current user's appointments
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def get(self, request):
        """Get user's appointments"""
        # Set filters based on user type
        filters = {"is_upcoming": True}

        if request.user.user_type == "patient":
            filters["patient_id"] = str(request.user.user_id)
        elif request.user.user_type == "specialist":
            if hasattr(request.user, "specialist_profile"):
                filters["specialist_id"] = request.user.specialist_profile.id

        # Get appointments
        appointments, pagination = AppointmentService.search_appointments(
            filters=filters,
            user=request.user,
            page=1,
            page_size=10,  # Limit for "my appointments" view
        )

        serializer = AppointmentSerializer(appointments, many=True)

        return APIResponse.success(
            message="Your upcoming appointments",
            data=serializer.data,
            pagination=pagination,
        )


class TodayAppointmentsView(APIView):
    """
    GET /api/appointments/today/
    Get today's appointments (for specialists and staff)
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_specialist, user_is_admin_or_staff])
    def get(self, request):
        """Get today's appointments"""
        today = timezone.now().date()

        # Set filters
        filters = {
            "appointment_date": today,
            "ordering": "start_time",
        }

        if request.user.user_type == "specialist":
            if hasattr(request.user, "specialist_profile"):
                filters["specialist_id"] = request.user.specialist_profile.id

        # Get today's appointments
        appointments, pagination = AppointmentService.search_appointments(
            filters=filters,
            user=request.user,
            page=1,
            page_size=50,  # Likely won't have 50 appointments in one day
        )

        # Group by status for easier display
        appointments_by_status = {
            "scheduled": [],
            "confirmed": [],
            "in_progress": [],
            "completed": [],
        }

        for appointment in appointments:
            if appointment.status in appointments_by_status:
                serializer = AppointmentSerializer(appointment)
                appointments_by_status[appointment.status].append(serializer.data)

        return APIResponse.success(
            message=f"Today's appointments ({today})",
            data={
                "date": today.isoformat(),
                "appointments_by_status": appointments_by_status,
                "total_appointments": len(appointments),
            },
        )
