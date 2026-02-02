from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timedelta
from apps.appointments.services import AppointmentService
from apps.appointments.models import Appointment
from apps.specialists.models import Specialist
from apps.users.models import User
from core.exceptions.base_exceptions import (
    ValidationError,
    BusinessRuleError,
    ConflictError,
)


class AppointmentServiceTestCase(TestCase):
    """Test suite for AppointmentService business logic"""

    def setUp(self):
        """Set up test data"""
        # Create users
        self.patient_user = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
            user_type="patient",
        )

        self.specialist_user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            first_name="Dr. Jane",
            last_name="Smith",
            user_type="specialist",
        )

        # Create specialist
        self.specialist = Specialist.objects.create(
            user=self.specialist_user,
            license_number="LIC123456",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=100.00,
            is_accepting_new_patients=True,
        )

        # Add is_active attribute if not in model
        self.specialist.is_active = True

    # =============================================
    # Tests for _normalize_datetime
    # =============================================

    def test_normalize_datetime_valid_aware_datetime(self):
        """Test normalization with timezone-aware datetime"""
        aware_dt = timezone.now()
        result = AppointmentService._normalize_datetime(aware_dt)
        self.assertEqual(result, aware_dt)
        self.assertTrue(timezone.is_aware(result))

    def test_normalize_datetime_valid_naive_datetime(self):
        """Test normalization with naive datetime - should make it aware"""
        naive_dt = datetime(2026, 6, 10, 10, 0, 0)
        result = AppointmentService._normalize_datetime(naive_dt)
        self.assertTrue(timezone.is_aware(result))

    def test_normalize_datetime_invalid_type(self):
        """Test normalization with invalid type"""
        with self.assertRaises(ValidationError):
            AppointmentService._normalize_datetime("not a datetime")

        with self.assertRaises(ValidationError):
            AppointmentService._normalize_datetime(123456)

    # =============================================
    # Tests for is_within_clinic_hours
    # =============================================

    def test_is_within_clinic_hours_success(self):
        """Test valid appointment time within clinic hours"""
        appointment_date = timezone.datetime(2026, 6, 10, 10, 0, 0)
        result = AppointmentService.is_within_clinic_hours(appointment_date)
        self.assertTrue(result)

    def test_is_within_clinic_hours_at_opening(self):
        """Test appointment at clinic opening time (9 AM)"""
        appointment_date = timezone.datetime(2026, 6, 10, 9, 0, 0)
        result = AppointmentService.is_within_clinic_hours(appointment_date)
        self.assertTrue(result)

    def test_is_within_clinic_hours_before_closing(self):
        """Test appointment just before closing time (6:59 PM)"""
        appointment_date = timezone.datetime(2026, 6, 10, 18, 59, 0)
        result = AppointmentService.is_within_clinic_hours(appointment_date)
        self.assertTrue(result)

    def test_is_within_clinic_hours_invalid_data_type(self):
        """Test with invalid data type"""
        with self.assertRaises(ValidationError):
            AppointmentService.is_within_clinic_hours(123456)

    def test_is_within_clinic_hours_outside_hours(self):
        """Test appointment outside clinic hours"""
        appointment_night_date = timezone.datetime(2026, 2, 2, 22, 0, 0)
        result = AppointmentService.is_within_clinic_hours(appointment_night_date)
        self.assertFalse(result)

    def test_is_within_clinic_hours_before_opening(self):
        """Test appointment before clinic opens (8 AM)"""
        appointment_date = timezone.datetime(2026, 6, 10, 8, 0, 0)
        result = AppointmentService.is_within_clinic_hours(appointment_date)
        self.assertFalse(result)

    def test_is_within_clinic_hours_at_closing(self):
        """Test appointment at closing time (7 PM) - should be False"""
        appointment_date = timezone.datetime(2026, 6, 10, 19, 0, 0)
        result = AppointmentService.is_within_clinic_hours(appointment_date)
        self.assertFalse(result)

    # =============================================
    # Tests for validate_booking_time
    # =============================================

    def test_validate_booking_time_success(self):
        """Test valid booking time"""
        future_time = timezone.now() + timedelta(days=7, hours=2)
        future_time = future_time.replace(hour=10, minute=0)
        # Should not raise any exception
        AppointmentService.validate_booking_time(future_time)

    def test_validate_booking_time_past_time(self):
        """Test booking time in the past"""
        past_time = timezone.now() - timedelta(hours=1)
        with self.assertRaises(BusinessRuleError) as context:
            AppointmentService.validate_booking_time(past_time)
        self.assertIn("future time", str(context.exception))

    def test_validate_booking_time_too_soon(self):
        """Test booking time less than minimum advance time"""
        too_soon = timezone.now() + timedelta(minutes=30)
        with self.assertRaises(BusinessRuleError) as context:
            AppointmentService.validate_booking_time(too_soon)
        self.assertIn("at least", str(context.exception))

    def test_validate_booking_time_too_far(self):
        """Test booking time beyond maximum advance booking"""
        too_far = timezone.now() + timedelta(days=100)
        with self.assertRaises(BusinessRuleError) as context:
            AppointmentService.validate_booking_time(too_far)
        self.assertIn("cannot be booked more than", str(context.exception))

    def test_validate_booking_time_outside_clinic_hours(self):
        """Test booking time outside clinic operating hours"""
        future_date = timezone.now() + timedelta(days=7)
        outside_hours = future_date.replace(hour=20, minute=0)
        with self.assertRaises(BusinessRuleError) as context:
            AppointmentService.validate_booking_time(outside_hours)
        self.assertIn("must be scheduled between", str(context.exception))

    def test_validate_booking_time_weekend(self):
        """Test booking time on weekend"""
        # Find next Saturday
        future_date = timezone.now() + timedelta(days=7)
        days_until_saturday = (5 - future_date.weekday()) % 7
        saturday = future_date + timedelta(days=days_until_saturday)
        saturday = saturday.replace(hour=10, minute=0)

        with self.assertRaises(BusinessRuleError) as context:
            AppointmentService.validate_booking_time(saturday)
        self.assertIn("weekdays", str(context.exception))

    # =============================================
    # Tests for validate_appointment_time_slot
    # =============================================

    def test_validate_appointment_time_slot_success(self):
        """Test valid appointment time slot"""
        start = timezone.now() + timedelta(days=7)
        end = start + timedelta(minutes=30)
        # Should not raise any exception
        AppointmentService.validate_appointment_time_slot(start, end)

    def test_validate_appointment_time_slot_15_minutes(self):
        """Test valid 15-minute appointment"""
        start = timezone.now() + timedelta(days=7)
        end = start + timedelta(minutes=15)
        AppointmentService.validate_appointment_time_slot(start, end)

    def test_validate_appointment_time_slot_60_minutes(self):
        """Test valid 60-minute appointment"""
        start = timezone.now() + timedelta(days=7)
        end = start + timedelta(minutes=60)
        AppointmentService.validate_appointment_time_slot(start, end)

    def test_validate_appointment_time_slot_too_short(self):
        """Test appointment duration less than minimum"""
        start = timezone.now() + timedelta(days=7)
        end = start + timedelta(minutes=10)
        with self.assertRaises(BusinessRuleError) as context:
            AppointmentService.validate_appointment_time_slot(start, end)
        self.assertIn("Minimum appointment duration", str(context.exception))

    def test_validate_appointment_time_slot_invalid_increment(self):
        """Test appointment duration not in 15-minute increments"""
        start = timezone.now() + timedelta(days=7)
        end = start + timedelta(minutes=20)
        with self.assertRaises(BusinessRuleError) as context:
            AppointmentService.validate_appointment_time_slot(start, end)
        self.assertIn("15-minute increments", str(context.exception))

    def test_validate_appointment_time_slot_too_long(self):
        """Test appointment duration exceeds maximum"""
        start = timezone.now() + timedelta(days=7)
        end = start + timedelta(minutes=150)
        with self.assertRaises(BusinessRuleError) as context:
            AppointmentService.validate_appointment_time_slot(start, end)
        self.assertIn("Maximum appointment duration", str(context.exception))

    # =============================================
    # Tests for check_specialist_availability
    # =============================================

    def test_check_specialist_availability_success(self):
        """Test specialist is available for time slot"""
        start = timezone.now() + timedelta(days=7, hours=2)
        end = start + timedelta(minutes=30)
        # Should not raise any exception
        AppointmentService.check_specialist_availability(self.specialist, start, end)

    def test_check_specialist_availability_inactive_specialist(self):
        """Test booking with inactive specialist"""
        self.specialist.is_active = False
        start = timezone.now() + timedelta(days=7, hours=2)
        end = start + timedelta(minutes=30)

        with self.assertRaises(BusinessRuleError) as context:
            AppointmentService.check_specialist_availability(
                self.specialist, start, end
            )
        self.assertIn("not active", str(context.exception))

    def test_check_specialist_availability_conflict(self):
        """Test specialist has conflicting appointment"""
        start = timezone.now() + timedelta(days=7, hours=2)
        end = start + timedelta(minutes=30)

        # Create existing appointment
        Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=start,
            start_time=start,
            end_time=end,
            duration_minutes=30,
            status="scheduled",
        )

        # Try to book overlapping time
        with self.assertRaises(ConflictError) as context:
            AppointmentService.check_specialist_availability(
                self.specialist, start, end
            )
        self.assertIn("already has an appointment", str(context.exception))

    def test_check_specialist_availability_exclude_current(self):
        """Test specialist availability excluding current appointment"""
        start = timezone.now() + timedelta(days=7, hours=2)
        end = start + timedelta(minutes=30)

        # Create existing appointment
        existing = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=start,
            start_time=start,
            end_time=end,
            duration_minutes=30,
            status="scheduled",
        )

        # Should not raise when excluding current appointment
        AppointmentService.check_specialist_availability(
            self.specialist, start, end, exclude_appointment_id=existing.id
        )

    # =============================================
    # Tests for check_patient_availability
    # =============================================

    def test_check_patient_availability_success(self):
        """Test patient is available for time slot"""
        start = timezone.now() + timedelta(days=7, hours=2)
        end = start + timedelta(minutes=30)
        # Should not raise any exception
        AppointmentService.check_patient_availability(self.patient_user, start, end)

    def test_check_patient_availability_conflict(self):
        """Test patient has conflicting appointment"""
        start = timezone.now() + timedelta(days=7, hours=2)
        end = start + timedelta(minutes=30)

        # Create existing appointment
        Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=start,
            start_time=start,
            end_time=end,
            duration_minutes=30,
            status="confirmed",
        )

        # Try to book overlapping time
        with self.assertRaises(ConflictError) as context:
            AppointmentService.check_patient_availability(self.patient_user, start, end)
        self.assertIn("Patient already has", str(context.exception))

    def test_check_patient_availability_exclude_current(self):
        """Test patient availability excluding current appointment"""
        start = timezone.now() + timedelta(days=7, hours=2)
        end = start + timedelta(minutes=30)

        # Create existing appointment
        existing = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=start,
            start_time=start,
            end_time=end,
            duration_minutes=30,
            status="scheduled",
        )

        # Should not raise when excluding current appointment
        AppointmentService.check_patient_availability(
            self.patient_user, start, end, exclude_appointment_id=existing.id
        )

    # =============================================
    # Tests for cancel_appointment
    # =============================================

    def test_cancel_appointment_success(self):
        """Test successful appointment cancellation"""
        start = timezone.now() + timedelta(days=7, hours=2)
        end = start + timedelta(minutes=30)

        appointment = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=start,
            start_time=start,
            end_time=end,
            duration_minutes=30,
            status="scheduled",
        )

        cancelled = AppointmentService.cancel_appointment(
            appointment, self.patient_user, "Personal reasons"
        )

        self.assertEqual(cancelled.status, "cancelled")
        self.assertIn("Personal reasons", cancelled.notes)

    def test_cancel_appointment_already_completed(self):
        """Test cancelling already completed appointment"""
        start = timezone.now() - timedelta(days=1)
        end = start + timedelta(minutes=30)

        appointment = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=start,
            start_time=start,
            end_time=end,
            duration_minutes=30,
            status="completed",
        )

        with self.assertRaises(BusinessRuleError) as context:
            AppointmentService.cancel_appointment(appointment, self.patient_user)
        self.assertIn("Cannot cancel", str(context.exception))

    def test_cancel_appointment_late_cancellation(self):
        """Test late cancellation (less than 24 hours notice)"""
        start = timezone.now() + timedelta(hours=12)
        end = start + timedelta(minutes=30)

        appointment = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=start,
            start_time=start,
            end_time=end,
            duration_minutes=30,
            status="scheduled",
        )

        with self.assertRaises(BusinessRuleError) as context:
            AppointmentService.cancel_appointment(appointment, self.patient_user)
        self.assertIn("24 hours in advance", str(context.exception))

    # =============================================
    # Tests for get_appointment_statistics
    # =============================================

    def test_get_appointment_statistics_no_appointments(self):
        """Test statistics when no appointments exist"""
        stats = AppointmentService.get_appointment_statistics(period="month")
        self.assertEqual(stats["total_appointments"], 0)
        self.assertIn("No appointments found", stats["message"])

    def test_get_appointment_statistics_with_data(self):
        """Test statistics with appointment data"""
        start = timezone.now() + timedelta(days=1, hours=2)
        end = start + timedelta(minutes=30)

        # Create test appointments
        Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=start,
            start_time=start,
            end_time=end,
            duration_minutes=30,
            status="scheduled",
        )

        Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_type="therapy",
            appointment_date=start + timedelta(days=1),
            start_time=start + timedelta(days=1),
            end_time=end + timedelta(days=1),
            duration_minutes=45,
            status="confirmed",
        )

        stats = AppointmentService.get_appointment_statistics(period="month")
        self.assertEqual(stats["total_appointments"], 2)
        self.assertIn("status_distribution", stats)
        self.assertIn("type_distribution", stats)
        self.assertIn("averages", stats)

    def test_get_appointment_statistics_filter_by_specialist(self):
        """Test statistics filtered by specialist"""
        start = timezone.now() + timedelta(days=1, hours=2)
        end = start + timedelta(minutes=30)

        Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=start,
            start_time=start,
            end_time=end,
            duration_minutes=30,
            status="scheduled",
        )

        stats = AppointmentService.get_appointment_statistics(
            period="month", specialist_id=self.specialist.id
        )
        self.assertEqual(stats["total_appointments"], 1)
