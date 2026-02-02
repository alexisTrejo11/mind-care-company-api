from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
from datetime import date, time
from apps.specialists.models import Specialist, Service, SpecialistService, Availability

User = get_user_model()


class SpecialistModelTest(TestCase):
    """Test cases for Specialist model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
            user_type="specialist",
        )

    def test_create_specialist_success(self):
        """Test creating a valid specialist"""
        specialist = Specialist.objects.create(
            user=self.user,
            license_number="LIC12345",
            specialization="psychologist",
            qualifications="PhD in Psychology",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
            is_accepting_new_patients=True,
            is_active=True,
            max_daily_appointments=20,
            bio="Experienced psychologist",
            rating=Decimal("4.50"),
        )

        self.assertEqual(specialist.user, self.user)
        self.assertEqual(specialist.license_number, "LIC12345")
        self.assertEqual(specialist.specialization, "psychologist")
        self.assertEqual(specialist.years_experience, 5)
        self.assertEqual(specialist.consultation_fee, Decimal("150.00"))
        self.assertTrue(specialist.is_accepting_new_patients)
        self.assertTrue(specialist.is_active)
        self.assertEqual(specialist.max_daily_appointments, 20)
        self.assertEqual(specialist.rating, Decimal("4.50"))

    def test_specialist_user_one_to_one_relationship(self):
        """Test one-to-one relationship between User and Specialist"""
        specialist = Specialist.objects.create(
            user=self.user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
        )

        self.assertEqual(self.user.specialist_profile, specialist)

    def test_specialist_license_number_unique(self):
        """Test that license number must be unique"""
        Specialist.objects.create(
            user=self.user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
        )

        user2 = User.objects.create_user(
            email="specialist2@test.com",
            password="testpass123",
            user_type="specialist",
        )

        with self.assertRaises(IntegrityError):
            Specialist.objects.create(
                user=user2,
                license_number="LIC12345",  # Duplicate
                specialization="psychiatrist",
                years_experience=3,
                consultation_fee=Decimal("200.00"),
            )

    def test_specialist_negative_years_experience(self):
        """Test that years_experience cannot be negative"""
        specialist = Specialist(
            user=self.user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=-1,  # Invalid
            consultation_fee=Decimal("150.00"),
        )

        with self.assertRaises(ValidationError):
            specialist.full_clean()

    def test_specialist_negative_consultation_fee(self):
        """Test that consultation_fee cannot be negative"""
        specialist = Specialist(
            user=self.user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("-50.00"),  # Invalid
        )

        with self.assertRaises(ValidationError):
            specialist.full_clean()

    def test_specialist_invalid_rating(self):
        """Test that rating must be between 0 and 5"""
        # Test rating > 5
        specialist = Specialist(
            user=self.user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
            rating=Decimal("6.00"),  # Invalid
        )

        with self.assertRaises(ValidationError):
            specialist.full_clean()

        # Test rating < 0
        specialist.rating = Decimal("-1.00")
        with self.assertRaises(ValidationError):
            specialist.full_clean()

    def test_specialist_zero_max_daily_appointments(self):
        """Test that max_daily_appointments must be at least 1"""
        specialist = Specialist(
            user=self.user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
            max_daily_appointments=0,  # Invalid
        )

        with self.assertRaises(ValidationError):
            specialist.full_clean()

    def test_specialist_default_values(self):
        """Test default values for specialist fields"""
        specialist = Specialist.objects.create(
            user=self.user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
        )

        self.assertTrue(specialist.is_accepting_new_patients)
        self.assertTrue(specialist.is_active)
        self.assertEqual(specialist.max_daily_appointments, 20)
        self.assertEqual(specialist.rating, Decimal("0.00"))
        self.assertEqual(specialist.qualifications, "")
        self.assertEqual(specialist.bio, "")

    def test_specialist_can_handle_appointment_type(self):
        """Test can_handle_appointment_type method"""
        specialist = Specialist.objects.create(
            user=self.user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
        )

        # Currently returns True for all types
        self.assertTrue(specialist.can_handle_appointment_type("online"))
        self.assertTrue(specialist.can_handle_appointment_type("in_person"))
        self.assertTrue(specialist.can_handle_appointment_type("home_visit"))

    def test_specialist_user_cascade_delete(self):
        """Test that specialist is deleted when user is deleted"""
        specialist = Specialist.objects.create(
            user=self.user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
        )

        specialist_id = specialist.id
        self.user.delete()

        self.assertFalse(Specialist.objects.filter(id=specialist_id).exists())


class ServiceModelTest(TestCase):
    """Test cases for Service model"""

    def test_create_service_success(self):
        """Test creating a valid service"""
        service = Service.objects.create(
            name="Mental Health Consultation",
            description="Initial mental health assessment",
            category="mental_health",
            duration_minutes=60,
            base_price=Decimal("100.00"),
            is_active=True,
        )

        self.assertEqual(service.name, "Mental Health Consultation")
        self.assertEqual(service.category, "mental_health")
        self.assertEqual(service.duration_minutes, 60)
        self.assertEqual(service.base_price, Decimal("100.00"))
        self.assertTrue(service.is_active)

    def test_service_negative_duration(self):
        """Test that duration_minutes cannot be less than 5"""
        service = Service(
            name="Quick Check",
            category="mental_health",
            duration_minutes=3,  # Invalid
            base_price=Decimal("50.00"),
        )

        with self.assertRaises(ValidationError):
            service.full_clean()

    def test_service_negative_base_price(self):
        """Test that base_price cannot be negative"""
        service = Service(
            name="Free Service",
            category="mental_health",
            duration_minutes=30,
            base_price=Decimal("-10.00"),  # Invalid
        )

        with self.assertRaises(ValidationError):
            service.full_clean()

    def test_service_default_values(self):
        """Test default values for service fields"""
        service = Service.objects.create(
            name="Consultation",
            category="mental_health",
            duration_minutes=60,
            base_price=Decimal("100.00"),
        )

        self.assertTrue(service.is_active)
        self.assertEqual(service.description, "")

    def test_service_str_representation(self):
        """Test string representation of service"""
        service = Service.objects.create(
            name="Mental Health Consultation",
            category="mental_health",
            duration_minutes=60,
            base_price=Decimal("100.00"),
        )

        self.assertEqual(str(service), "Mental Health Consultation (Mental Health)")

    def test_service_meta_ordering(self):
        """Test service ordering by category and name"""
        Service.objects.create(
            name="Therapy",
            category="therapy",
            duration_minutes=60,
            base_price=Decimal("120.00"),
        )
        Service.objects.create(
            name="Assessment",
            category="mental_health",
            duration_minutes=45,
            base_price=Decimal("100.00"),
        )
        Service.objects.create(
            name="Consultation",
            category="mental_health",
            duration_minutes=30,
            base_price=Decimal("80.00"),
        )

        services = list(Service.objects.all())
        # Should be ordered by category, then name
        self.assertEqual(services[0].name, "Assessment")
        self.assertEqual(services[1].name, "Consultation")
        self.assertEqual(services[2].name, "Therapy")


class SpecialistServiceModelTest(TestCase):
    """Test cases for SpecialistService model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            user_type="specialist",
        )
        self.specialist = Specialist.objects.create(
            user=self.user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
        )
        self.service = Service.objects.create(
            name="Mental Health Consultation",
            category="mental_health",
            duration_minutes=60,
            base_price=Decimal("100.00"),
        )

    def test_create_specialist_service_success(self):
        """Test creating a valid specialist service"""
        specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
            price_override=Decimal("120.00"),
            is_available=True,
        )

        self.assertEqual(specialist_service.specialist, self.specialist)
        self.assertEqual(specialist_service.service, self.service)
        self.assertEqual(specialist_service.price_override, Decimal("120.00"))
        self.assertTrue(specialist_service.is_available)

    def test_specialist_service_unique_together(self):
        """Test that specialist-service combination must be unique"""
        SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
        )

        with self.assertRaises(IntegrityError):
            SpecialistService.objects.create(
                specialist=self.specialist,
                service=self.service,  # Duplicate combination
            )

    def test_specialist_service_relationship(self):
        """Test relationships between specialist and service"""
        specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
        )

        # Test related names
        self.assertIn(specialist_service, self.specialist.services.all())
        self.assertIn(specialist_service, self.service.specialists.all())

    def test_specialist_service_get_price_with_override(self):
        """Test get_price method with price override"""
        specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
            price_override=Decimal("120.00"),
        )

        self.assertEqual(specialist_service.get_price(), Decimal("120.00"))

    def test_specialist_service_get_price_without_override(self):
        """Test get_price method without price override"""
        specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
            price_override=None,
        )

        self.assertEqual(specialist_service.get_price(), Decimal("100.00"))

    def test_specialist_service_negative_price_override(self):
        """Test that price_override cannot be negative"""
        specialist_service = SpecialistService(
            specialist=self.specialist,
            service=self.service,
            price_override=Decimal("-50.00"),  # Invalid
        )

        with self.assertRaises(ValidationError):
            specialist_service.full_clean()

    def test_specialist_service_default_values(self):
        """Test default values for specialist service fields"""
        specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
        )

        self.assertTrue(specialist_service.is_available)
        self.assertIsNone(specialist_service.price_override)

    def test_specialist_service_str_representation(self):
        """Test string representation of specialist service"""
        specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
        )

        expected = f"{self.user.get_full_name()} - Mental Health Consultation"
        self.assertEqual(str(specialist_service), expected)

    def test_specialist_service_cascade_delete_specialist(self):
        """Test that specialist service is deleted when specialist is deleted"""
        specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
        )

        specialist_service_id = specialist_service.id
        self.specialist.delete()

        self.assertFalse(
            SpecialistService.objects.filter(id=specialist_service_id).exists()
        )

    def test_specialist_service_cascade_delete_service(self):
        """Test that specialist service is deleted when service is deleted"""
        specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
        )

        specialist_service_id = specialist_service.id
        self.service.delete()

        self.assertFalse(
            SpecialistService.objects.filter(id=specialist_service_id).exists()
        )


class AvailabilityModelTest(TestCase):
    """Test cases for Availability model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            user_type="specialist",
        )
        self.specialist = Specialist.objects.create(
            user=self.user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
        )

    def test_create_availability_success(self):
        """Test creating a valid availability"""
        availability = Availability.objects.create(
            specialist=self.specialist,
            day_of_week=1,  # Monday
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_recurring=True,
            valid_from=date(2026, 2, 1),
            valid_until=date(2026, 12, 31),
        )

        self.assertEqual(availability.specialist, self.specialist)
        self.assertEqual(availability.day_of_week, 1)
        self.assertEqual(availability.start_time, time(9, 0))
        self.assertEqual(availability.end_time, time(17, 0))
        self.assertTrue(availability.is_recurring)
        self.assertEqual(availability.valid_from, date(2026, 2, 1))
        self.assertEqual(availability.valid_until, date(2026, 12, 31))

    def test_availability_relationship(self):
        """Test relationship between availability and specialist"""
        availability = Availability.objects.create(
            specialist=self.specialist,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(17, 0),
            valid_from=date(2026, 2, 1),
        )

        self.assertIn(availability, self.specialist.availability.all())

    def test_availability_default_values(self):
        """Test default values for availability fields"""
        availability = Availability.objects.create(
            specialist=self.specialist,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(17, 0),
            valid_from=date(2026, 2, 1),
        )

        self.assertTrue(availability.is_recurring)
        self.assertIsNone(availability.valid_until)

    def test_availability_str_representation(self):
        """Test string representation of availability"""
        availability = Availability.objects.create(
            specialist=self.specialist,
            day_of_week=1,  # Monday
            start_time=time(9, 0),
            end_time=time(17, 0),
            valid_from=date(2026, 2, 1),
        )

        expected = f"{self.user.get_full_name()} - Monday 09:00:00-17:00:00"
        self.assertEqual(str(availability), expected)

    def test_availability_day_of_week_choices(self):
        """Test all day of week choices"""
        days = [0, 1, 2, 3, 4, 5, 6]  # Sunday to Saturday

        for day in days:
            availability = Availability.objects.create(
                specialist=self.specialist,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(17, 0),
                valid_from=date(2026, 2, 1),
            )
            self.assertEqual(availability.day_of_week, day)

    def test_availability_meta_ordering(self):
        """Test availability ordering by specialist, day, and start time"""
        Availability.objects.create(
            specialist=self.specialist,
            day_of_week=2,  # Tuesday
            start_time=time(14, 0),
            end_time=time(17, 0),
            valid_from=date(2026, 2, 1),
        )
        Availability.objects.create(
            specialist=self.specialist,
            day_of_week=1,  # Monday
            start_time=time(9, 0),
            end_time=time(12, 0),
            valid_from=date(2026, 2, 1),
        )
        Availability.objects.create(
            specialist=self.specialist,
            day_of_week=1,  # Monday
            start_time=time(14, 0),
            end_time=time(17, 0),
            valid_from=date(2026, 2, 1),
        )

        availabilities = list(Availability.objects.all())
        # Should be ordered by specialist, day_of_week, start_time
        self.assertEqual(availabilities[0].day_of_week, 1)
        self.assertEqual(availabilities[0].start_time, time(9, 0))
        self.assertEqual(availabilities[1].day_of_week, 1)
        self.assertEqual(availabilities[1].start_time, time(14, 0))
        self.assertEqual(availabilities[2].day_of_week, 2)

    def test_availability_cascade_delete_specialist(self):
        """Test that availability is deleted when specialist is deleted"""
        availability = Availability.objects.create(
            specialist=self.specialist,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(17, 0),
            valid_from=date(2026, 2, 1),
        )

        availability_id = availability.id
        self.specialist.delete()

        self.assertFalse(Availability.objects.filter(id=availability_id).exists())

    def test_availability_multiple_slots_same_day(self):
        """Test creating multiple availability slots for the same day"""
        morning = Availability.objects.create(
            specialist=self.specialist,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(12, 0),
            valid_from=date(2026, 2, 1),
        )
        afternoon = Availability.objects.create(
            specialist=self.specialist,
            day_of_week=1,
            start_time=time(14, 0),
            end_time=time(17, 0),
            valid_from=date(2026, 2, 1),
        )

        slots = Availability.objects.filter(specialist=self.specialist, day_of_week=1)
        self.assertEqual(slots.count(), 2)
        self.assertIn(morning, slots)
        self.assertIn(afternoon, slots)

    def test_availability_non_recurring(self):
        """Test creating non-recurring availability"""
        availability = Availability.objects.create(
            specialist=self.specialist,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_recurring=False,
            valid_from=date(2026, 2, 3),
            valid_until=date(2026, 2, 3),  # Single day
        )

        self.assertFalse(availability.is_recurring)
        self.assertEqual(availability.valid_from, availability.valid_until)
