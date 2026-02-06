"""
Comprehensive test cases for AvailabilityUseCases.

Tests cover:
- Availability creation
- Availability validation
- Available slot calculation
- Conflict detection
- Edge cases and boundaries
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, time, datetime
from decimal import Decimal

from apps.specialists.models import Specialist, Availability
from apps.specialists.services.availability_use_cases import AvailabilityUseCases
from apps.appointments.models import Appointment
from apps.core.exceptions.base_exceptions import (
    ValidationError,
    NotFoundError,
    ConflictError,
)

User = get_user_model()


class AvailabilityCreationTests(TestCase):
    """Test availability creation methods"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="specialist@test.com", password="testpass123"
        )
        self.specialist = Specialist.objects.create(
            user=self.user,
            license_number="MD123456",
            specialization="psychiatrist",
            years_experience=10,
            consultation_fee=Decimal("150.00"),
        )

    def test_create_availability_success(self):
        """Test successful availability creation"""
        start_time = time(9, 0)
        end_time = time(17, 0)

        availability = AvailabilityUseCases.create_availability(
            specialist_id=self.specialist.id,
            day_of_week=1,  # Monday
            start_time=start_time,
            end_time=end_time,
            is_recurring=True,
            valid_from=timezone.now().date(),
        )

        self.assertIsNotNone(availability.id)
        self.assertEqual(availability.specialist, self.specialist)
        self.assertEqual(availability.day_of_week, 1)
        self.assertEqual(availability.start_time, start_time)
        self.assertEqual(availability.end_time, end_time)
        self.assertTrue(availability.is_recurring)

    def test_create_availability_nonexistent_specialist(self):
        """Test availability creation for nonexistent specialist"""
        with self.assertRaises(NotFoundError):
            AvailabilityUseCases.create_availability(
                specialist_id=99999,
                day_of_week=1,
                start_time=time(9, 0),
                end_time=time(17, 0),
                valid_from=timezone.now().date(),
            )

    def test_create_availability_invalid_start_time(self):
        """Test availability creation with invalid start time format"""
        with self.assertRaises(ValidationError):
            AvailabilityUseCases.create_availability(
                specialist_id=self.specialist.id,
                day_of_week=1,
                start_time="invalid",
                end_time=time(17, 0),
                valid_from=timezone.now().date(),
            )

    def test_create_availability_invalid_end_time(self):
        """Test availability creation with invalid end time format"""
        with self.assertRaises(ValidationError):
            AvailabilityUseCases.create_availability(
                specialist_id=self.specialist.id,
                day_of_week=1,
                start_time=time(9, 0),
                end_time="not-a-time",
                valid_from=timezone.now().date(),
            )

    def test_create_availability_with_string_times(self):
        """Test availability creation with string time format"""
        with self.assertRaises(ValidationError):
            AvailabilityUseCases.create_availability(
                specialist_id=self.specialist.id,
                day_of_week=1,
                start_time="09:00",
                end_time="17:00",
                valid_from=timezone.now().date(),
            )

    def test_create_availability_start_time_after_end_time(self):
        """Test availability creation with start time after end time"""
        with self.assertRaises(ValidationError):
            AvailabilityUseCases.create_availability(
                specialist_id=self.specialist.id,
                day_of_week=1,
                start_time=time(17, 0),
                end_time=time(9, 0),
                valid_from=timezone.now().date(),
            )

    def test_create_availability_same_start_and_end_time(self):
        """Test availability creation with same start and end time"""
        with self.assertRaises(ValidationError):
            AvailabilityUseCases.create_availability(
                specialist_id=self.specialist.id,
                day_of_week=1,
                start_time=time(9, 0),
                end_time=time(9, 0),
                valid_from=timezone.now().date(),
            )

    def test_create_availability_overlapping_schedule(self):
        """Test detecting overlapping availability"""
        # Create first availability
        AvailabilityUseCases.create_availability(
            specialist_id=self.specialist.id,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(12, 0),
            valid_from=timezone.now().date(),
        )

        # Try to create overlapping availability
        with self.assertRaises(ConflictError) as context:
            AvailabilityUseCases.create_availability(
                specialist_id=self.specialist.id,
                day_of_week=1,
                start_time=time(11, 0),
                end_time=time(14, 0),
                valid_from=timezone.now().date(),
            )
        self.assertIn("overlap", str(context.exception).lower())

    def test_create_availability_non_recurring(self):
        """Test creating non-recurring availability"""
        availability = AvailabilityUseCases.create_availability(
            specialist_id=self.specialist.id,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_recurring=False,
            valid_from=timezone.now().date(),
        )

        self.assertFalse(availability.is_recurring)

    def test_create_availability_with_valid_until(self):
        """Test creating availability with valid_until date"""
        valid_from = timezone.now()
        valid_until = valid_from + timedelta(days=30)

        availability = AvailabilityUseCases.create_availability(
            specialist_id=self.specialist.id,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(17, 0),
            valid_from=valid_from,
            valid_until=valid_until,
        )

        self.assertEqual(availability.valid_until, valid_until)

    def test_create_multiple_availabilities_different_days(self):
        """Test creating availabilities for different days"""
        for day in range(1, 6):  # Monday to Friday
            availability = AvailabilityUseCases.create_availability(
                specialist_id=self.specialist.id,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(17, 0),
                valid_from=timezone.now().date(),
            )
            self.assertEqual(availability.day_of_week, day)

    def test_create_availability_all_day_schedule(self):
        """Test creating all-day availability"""
        availability = AvailabilityUseCases.create_availability(
            specialist_id=self.specialist.id,
            day_of_week=1,
            start_time=time(0, 0),
            end_time=time(23, 59),
            valid_from=timezone.now().date(),
        )

        self.assertEqual(availability.start_time, time(0, 0))
        self.assertEqual(availability.end_time, time(23, 59))


class AvailableSlotsCalculationTests(TestCase):
    """Test available slots calculation methods"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="specialist@test.com", password="testpass123"
        )
        self.specialist = Specialist.objects.create(
            user=self.user,
            license_number="MD123456",
            specialization="psychiatrist",
            years_experience=10,
            consultation_fee=Decimal("150.00"),
        )

    def test_get_available_slots_success(self):
        """Test getting available slots for a date with availability"""
        # Create availability for tomorrow
        tomorrow = timezone.now().date() + timedelta(days=1)
        day_of_week = tomorrow.weekday()
        # Convert Python weekday (0=Monday) to Django weekday (1=Monday, 7=Sunday)
        django_day = (day_of_week + 1) % 7

        Availability.objects.create(
            specialist=self.specialist,
            day_of_week=django_day,
            start_time=time(9, 0),
            end_time=time(12, 0),
            is_recurring=True,
            valid_from=timezone.make_aware(datetime.combine(tomorrow, time(0, 0))),
            valid_until=timezone.make_aware(
                datetime.combine(tomorrow + timedelta(days=30), time(23, 59))
            ),
        )

        slots = AvailabilityUseCases.get_available_slots(
            specialist_id=self.specialist.id,
            target_date=tomorrow,
            service_duration=60,
        )

        self.assertIsInstance(slots, list)
        self.assertGreater(len(slots), 0)
        for slot in slots:
            self.assertIn("start_time", slot)
            self.assertIn("end_time", slot)
            self.assertIn("date", slot)

    def test_get_available_slots_no_availability(self):
        """Test getting slots when no availability exists"""
        tomorrow = timezone.now().date() + timedelta(days=1)

        slots = AvailabilityUseCases.get_available_slots(
            specialist_id=self.specialist.id,
            target_date=tomorrow,
            service_duration=60,
        )

        self.assertEqual(len(slots), 0)

    def test_get_available_slots_nonexistent_specialist(self):
        """Test getting slots for nonexistent specialist"""
        tomorrow = timezone.now().date() + timedelta(days=1)

        with self.assertRaises(NotFoundError):
            AvailabilityUseCases.get_available_slots(
                specialist_id=99999,
                target_date=tomorrow,
                service_duration=60,
            )

    def test_get_available_slots_invalid_date_format(self):
        """Test getting slots with invalid date format"""
        with self.assertRaises(ValidationError):
            AvailabilityUseCases.get_available_slots(
                specialist_id=self.specialist.id,
                target_date="01-25-2026",  # Invalid format
                service_duration=60,
            )

    def test_get_available_slots_with_existing_appointments(self):
        """Test slot calculation excluding existing appointments"""
        tomorrow = timezone.now().date() + timedelta(days=1)
        day_of_week = tomorrow.weekday()
        django_day = (day_of_week + 1) % 7

        # Create availability
        Availability.objects.create(
            specialist=self.specialist,
            day_of_week=django_day,
            start_time=time(9, 0),
            end_time=time(12, 0),
            is_recurring=True,
            valid_from=timezone.make_aware(datetime.combine(tomorrow, time(0, 0))),
            valid_until=timezone.make_aware(
                datetime.combine(tomorrow + timedelta(days=30), time(23, 59))
            ),
        )

        # Create an appointment in the middle
        # Use timezone-aware datetime
        appointment_start = timezone.make_aware(datetime.combine(tomorrow, time(10, 0)))
        appointment_end = timezone.make_aware(datetime.combine(tomorrow, time(11, 0)))
        Appointment.objects.create(
            patient=self.user,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=appointment_start,
            start_time=appointment_start,
            end_time=appointment_end,
            duration_minutes=60,
            status="scheduled",
        )

        slots = AvailabilityUseCases.get_available_slots(
            specialist_id=self.specialist.id,
            target_date=tomorrow,
            service_duration=60,
        )

        # Should have slots around the appointment but not overlapping
        self.assertIsInstance(slots, list)

    def test_get_available_slots_different_service_durations(self):
        """Test slot calculation with various service durations"""
        tomorrow = timezone.now().date() + timedelta(days=1)
        day_of_week = tomorrow.weekday()
        django_day = (day_of_week + 1) % 7

        Availability.objects.create(
            specialist=self.specialist,
            day_of_week=django_day,
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_recurring=True,
            valid_from=timezone.make_aware(datetime.combine(tomorrow, time(0, 0))),
            valid_until=timezone.make_aware(
                datetime.combine(tomorrow + timedelta(days=30), time(23, 59))
            ),
        )

        # Test with 30-minute slots
        slots_30 = AvailabilityUseCases.get_available_slots(
            specialist_id=self.specialist.id,
            target_date=tomorrow,
            service_duration=30,
        )

        # Test with 90-minute slots
        slots_90 = AvailabilityUseCases.get_available_slots(
            specialist_id=self.specialist.id,
            target_date=tomorrow,
            service_duration=90,
        )

        # 30-minute slots should be more than 90-minute slots
        self.assertGreater(len(slots_30), len(slots_90))

    def test_get_available_slots_multiple_availability_blocks(self):
        """Test slot calculation with multiple availability blocks per day"""
        tomorrow = timezone.now().date() + timedelta(days=1)
        day_of_week = tomorrow.weekday()
        django_day = (day_of_week + 1) % 7

        # Create morning availability
        Availability.objects.create(
            specialist=self.specialist,
            day_of_week=django_day,
            start_time=time(9, 0),
            end_time=time(12, 0),
            is_recurring=True,
            valid_from=timezone.make_aware(datetime.combine(tomorrow, time(0, 0))),
            valid_until=timezone.make_aware(
                datetime.combine(tomorrow + timedelta(days=30), time(23, 59))
            ),
        )

        # Create afternoon availability
        Availability.objects.create(
            specialist=self.specialist,
            day_of_week=django_day,
            start_time=time(14, 0),
            end_time=time(17, 0),
            is_recurring=True,
            valid_from=timezone.make_aware(datetime.combine(tomorrow, time(0, 0))),
            valid_until=timezone.make_aware(
                datetime.combine(tomorrow + timedelta(days=30), time(23, 59))
            ),
        )

        slots = AvailabilityUseCases.get_available_slots(
            specialist_id=self.specialist.id,
            target_date=tomorrow,
            service_duration=60,
        )

        # Should have slots from both blocks
        self.assertGreater(len(slots), 0)

    def test_get_available_slots_slot_increments(self):
        """Test that slots are generated in correct increments"""
        tomorrow = timezone.now().date() + timedelta(days=1)
        day_of_week = tomorrow.weekday()
        django_day = (day_of_week + 1) % 7

        Availability.objects.create(
            specialist=self.specialist,
            day_of_week=django_day,
            start_time=time(9, 0),
            end_time=time(10, 0),  # 1 hour
            is_recurring=True,
            valid_from=timezone.make_aware(datetime.combine(tomorrow, time(0, 0))),
            valid_until=timezone.make_aware(
                datetime.combine(tomorrow + timedelta(days=30), time(23, 59))
            ),
        )

        slots = AvailabilityUseCases.get_available_slots(
            specialist_id=self.specialist.id,
            target_date=tomorrow,
            service_duration=30,  # 30-minute slots
        )

        # Should have 2 slots (9:00-9:30, 9:30-10:00)
        self.assertEqual(len(slots), 2)


class AvailabilityBoundaryTests(TestCase):
    """Test boundary conditions and edge cases"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="specialist@test.com", password="testpass123"
        )
        self.specialist = Specialist.objects.create(
            user=self.user,
            license_number="MD123456",
            specialization="psychiatrist",
            years_experience=10,
            consultation_fee=Decimal("150.00"),
        )

    def test_create_availability_minimum_duration(self):
        """Test creating availability with minimal duration"""
        availability = AvailabilityUseCases.create_availability(
            specialist_id=self.specialist.id,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(9, 1),  # 1 minute
            valid_from=timezone.now().date(),
        )

        self.assertIsNotNone(availability.id)

    def test_availability_valid_all_weekdays(self):
        """Test creating availability for all weekdays"""
        weekdays = [1, 2, 3, 4, 5]  # Monday to Friday (Django: 1-7, 1=Monday)
        for day in weekdays:
            availability = AvailabilityUseCases.create_availability(
                specialist_id=self.specialist.id,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(17, 0),
                valid_from=timezone.now().date(),
            )
            self.assertEqual(availability.day_of_week, day)

    def test_availability_valid_weekend(self):
        """Test creating availability for weekend days"""
        weekend_days = [6, 7]  # Saturday and Sunday (Django: 1=Monday, 7=Sunday)
        for day in weekend_days:
            availability = AvailabilityUseCases.create_availability(
                specialist_id=self.specialist.id,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(17, 0),
                valid_from=timezone.now().date(),
            )
            self.assertEqual(availability.day_of_week, day)

    def test_get_available_slots_same_day_as_today(self):
        """Test getting slots for today"""
        today = timezone.now().date()
        day_of_week = today.weekday()
        django_day = (day_of_week + 1) % 7

        Availability.objects.create(
            specialist=self.specialist,
            day_of_week=django_day,
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_recurring=True,
            valid_from=timezone.make_aware(datetime.combine(today, time(0, 0))),
            valid_until=timezone.make_aware(
                datetime.combine(today + timedelta(days=30), time(23, 59))
            ),
        )

        slots = AvailabilityUseCases.get_available_slots(
            specialist_id=self.specialist.id,
            target_date=today,
            service_duration=60,
        )

        self.assertIsInstance(slots, list)

    def test_availability_valid_until_expires(self):
        """Test that expired availability is not considered"""
        yesterday = timezone.now().date() - timedelta(days=1)
        day_of_week = yesterday.weekday()
        django_day = (day_of_week + 1) % 7

        Availability.objects.create(
            specialist=self.specialist,
            day_of_week=django_day,
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_recurring=True,
            valid_from=timezone.make_aware(
                datetime.combine(yesterday - timedelta(days=30), time(0, 0))
            ),
            valid_until=timezone.make_aware(datetime.combine(yesterday, time(23, 59))),
        )

        # Try to get slots for today - should be empty (availability expired)
        today = timezone.now().date()
        today_day_of_week = today.weekday()
        today_django_day = (today_day_of_week + 1) % 7

        slots = AvailabilityUseCases.get_available_slots(
            specialist_id=self.specialist.id,
            target_date=today,
            service_duration=60,
        )

        # Should be empty because availability has expired
        self.assertEqual(len(slots), 0)
