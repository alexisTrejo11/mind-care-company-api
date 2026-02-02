from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError as DRFValidationError
from decimal import Decimal
from datetime import date, time

from apps.specialists.models import Specialist, Service, SpecialistService, Availability
from apps.specialists.serializers import (
    ServiceSerializer,
    ServiceCreateSerializer,
    ServiceUpdateSerializer,
    ServiceSearchSerializer,
    ServiceStatsSerializer,
    AvailabilitySerializer,
    SpecialistSerializer,
    SpecialistDetailSerializer,
    SpecialistCreateSerializer,
    SpecialistUpdateSerializer,
    SpecialistSearchSerializer,
    SpecialistServiceSerializer,
    SpecialistServiceCreateSerializer,
)
from core.exceptions.base_exceptions import NotFoundError

User = get_user_model()


class ServiceSerializerTest(TestCase):
    """Test cases for ServiceSerializer"""

    def setUp(self):
        """Set up test data"""
        self.service = Service.objects.create(
            name="Mental Health Consultation",
            description="Initial assessment",
            category="mental_health",
            duration_minutes=60,
            base_price=Decimal("100.00"),
            is_active=True,
        )

    def test_serialize_service(self):
        """Test serializing a service"""
        serializer = ServiceSerializer(self.service)
        data = serializer.data

        self.assertEqual(data["id"], self.service.id)
        self.assertEqual(data["name"], "Mental Health Consultation")
        self.assertEqual(data["category"], "mental_health")
        self.assertEqual(data["duration_minutes"], 60)
        self.assertEqual(Decimal(data["base_price"]), Decimal("100.00"))
        self.assertTrue(data["is_active"])

    def test_deserialize_valid_service(self):
        """Test deserializing valid service data"""
        data = {
            "name": "Therapy Session",
            "description": "50-minute therapy",
            "category": "therapy",
            "duration_minutes": 50,
            "base_price": "120.00",
            "is_active": True,
        }

        serializer = ServiceSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        service = serializer.save()

        self.assertEqual(service.name, "Therapy Session")
        self.assertEqual(service.duration_minutes, 50)

    def test_validate_minimum_duration(self):
        """Test validation of minimum duration"""
        data = {
            "name": "Quick Check",
            "category": "mental_health",
            "duration_minutes": 3,  # Too short
            "base_price": "50.00",
        }

        serializer = ServiceSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("duration_minutes", serializer.errors)

    def test_validate_negative_price(self):
        """Test validation of negative price"""
        data = {
            "name": "Service",
            "category": "mental_health",
            "duration_minutes": 30,
            "base_price": "-10.00",  # Negative
        }

        serializer = ServiceSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("base_price", serializer.errors)

    def test_validate_duplicate_name_in_category(self):
        """Test validation of duplicate service name in same category"""
        data = {
            "name": "Mental Health Consultation",  # Duplicate
            "category": "mental_health",
            "duration_minutes": 45,
            "base_price": "90.00",
        }

        serializer = ServiceSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("already exists in category", str(serializer.errors))

    def test_allow_same_name_different_category(self):
        """Test allowing same name in different category"""
        data = {
            "name": "Mental Health Consultation",
            "category": "therapy",  # Different category
            "duration_minutes": 60,
            "base_price": "100.00",
        }

        serializer = ServiceSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class ServiceCreateSerializerTest(TestCase):
    """Test cases for ServiceCreateSerializer"""

    def test_create_service_success(self):
        """Test creating a service successfully"""
        data = {
            "name": "New Service",
            "description": "Test description",
            "category": "wellness",
            "duration_minutes": 45,
            "base_price": "75.00",
        }

        serializer = ServiceCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        service = serializer.save()

        self.assertEqual(service.name, "New Service")
        self.assertTrue(service.is_active)  # Default value

    def test_validate_max_duration(self):
        """Test validation of maximum duration"""
        data = {
            "name": "Long Service",
            "category": "wellness",
            "duration_minutes": 500,  # Too long
            "base_price": "200.00",
        }

        serializer = ServiceCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("Maximum service duration is 480 minutes", str(serializer.errors))

    def test_validate_field_level_duration(self):
        """Test field-level validation for duration"""
        data = {
            "name": "Service",
            "category": "wellness",
            "duration_minutes": 2,  # Below minimum
            "base_price": "50.00",
        }

        serializer = ServiceCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("duration_minutes", serializer.errors)


class ServiceUpdateSerializerTest(TestCase):
    """Test cases for ServiceUpdateSerializer"""

    def setUp(self):
        """Set up test data"""
        self.service = Service.objects.create(
            name="Original Service",
            category="mental_health",
            duration_minutes=60,
            base_price=Decimal("100.00"),
        )

    def test_update_service_success(self):
        """Test updating a service successfully"""
        data = {
            "name": "Updated Service",
            "duration_minutes": 90,
            "is_active": False,
        }

        serializer = ServiceUpdateSerializer(self.service, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        updated_service = serializer.save()

        self.assertEqual(updated_service.name, "Updated Service")
        self.assertEqual(updated_service.duration_minutes, 90)
        self.assertFalse(updated_service.is_active)

    def test_update_prevent_duplicate_name(self):
        """Test preventing duplicate name when updating"""
        Service.objects.create(
            name="Existing Service",
            category="mental_health",
            duration_minutes=45,
            base_price=Decimal("80.00"),
        )

        data = {
            "name": "Existing Service",  # Duplicate
            "category": "mental_health",
        }

        serializer = ServiceUpdateSerializer(self.service, data=data, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn("already exists in category", str(serializer.errors))


class ServiceSearchSerializerTest(TestCase):
    """Test cases for ServiceSearchSerializer"""

    def test_valid_search_params(self):
        """Test valid search parameters"""
        data = {
            "category": "mental_health",
            "min_duration": 30,
            "max_duration": 90,
            "min_price": "50.00",
            "max_price": "200.00",
            "active_only": True,
            "search": "consultation",
            "ordering": "-base_price",
        }

        serializer = ServiceSearchSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_default_values(self):
        """Test default values for search"""
        data = {}

        serializer = ServiceSearchSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertTrue(serializer.validated_data["active_only"])
        self.assertEqual(serializer.validated_data["ordering"], "name")

    def test_invalid_category(self):
        """Test invalid category choice"""
        data = {"category": "invalid_category"}

        serializer = ServiceSearchSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("category", serializer.errors)


class ServiceStatsSerializerTest(TestCase):
    """Test cases for ServiceStatsSerializer"""

    def test_valid_period_choices(self):
        """Test valid period choices"""
        periods = ["today", "week", "month", "year", "all_time"]

        for period in periods:
            data = {"period": period}
            serializer = ServiceStatsSerializer(data=data)
            self.assertTrue(serializer.is_valid())

    def test_invalid_period(self):
        """Test invalid period choice"""
        data = {"period": "invalid"}

        serializer = ServiceStatsSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("period", serializer.errors)

    def test_default_include_inactive(self):
        """Test default value for include_inactive"""
        data = {"period": "month"}

        serializer = ServiceStatsSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertFalse(serializer.validated_data["include_inactive"])


class AvailabilitySerializerTest(TestCase):
    """Test cases for AvailabilitySerializer"""

    def setUp(self):
        """Set up test data"""
        user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            user_type="specialist",
        )
        self.specialist = Specialist.objects.create(
            user=user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
        )
        self.availability = Availability.objects.create(
            specialist=self.specialist,
            day_of_week=1,  # Monday
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_recurring=True,
            valid_from=date(2026, 2, 1),
        )

    def test_serialize_availability(self):
        """Test serializing availability"""
        serializer = AvailabilitySerializer(self.availability)
        data = serializer.data

        self.assertEqual(data["id"], self.availability.id)
        self.assertEqual(data["day_of_week"], 1)
        self.assertEqual(data["day_name"], "Monday")
        self.assertEqual(data["start_time"], "09:00:00")
        self.assertEqual(data["end_time"], "17:00:00")
        self.assertTrue(data["is_recurring"])

    def test_day_name_method(self):
        """Test get_day_name method"""
        serializer = AvailabilitySerializer(self.availability)
        self.assertEqual(serializer.data["day_name"], "Monday")


class SpecialistSerializerTest(TestCase):
    """Test cases for SpecialistSerializer"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
            user_type="specialist",
        )
        self.specialist = Specialist.objects.create(
            user=self.user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
            rating=Decimal("4.50"),
        )

        # Add a service
        service = Service.objects.create(
            name="Consultation",
            category="mental_health",
            duration_minutes=60,
            base_price=Decimal("100.00"),
        )
        SpecialistService.objects.create(
            specialist=self.specialist,
            service=service,
            is_available=True,
        )

    def test_serialize_specialist(self):
        """Test serializing a specialist"""
        serializer = SpecialistSerializer(self.specialist)
        data = serializer.data

        self.assertEqual(data["id"], self.specialist.id)
        self.assertEqual(data["specialist_name"], "John Doe")
        self.assertEqual(data["email"], "specialist@test.com")
        self.assertEqual(data["license_number"], "LIC12345")
        self.assertEqual(data["specialization"], "psychologist")
        self.assertEqual(data["years_experience"], 5)
        self.assertEqual(Decimal(data["rating"]), Decimal("4.50"))
        self.assertEqual(data["service_count"], 1)

    def test_get_specialist_name(self):
        """Test get_specialist_name method"""
        serializer = SpecialistSerializer(self.specialist)
        self.assertEqual(serializer.data["specialist_name"], "John Doe")

    def test_get_email(self):
        """Test get_email method"""
        serializer = SpecialistSerializer(self.specialist)
        self.assertEqual(serializer.data["email"], "specialist@test.com")

    def test_get_service_count(self):
        """Test get_service_count method"""
        serializer = SpecialistSerializer(self.specialist)
        self.assertEqual(serializer.data["service_count"], 1)


class SpecialistDetailSerializerTest(TestCase):
    """Test cases for SpecialistDetailSerializer"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
            user_type="specialist",
        )
        self.user.phone = "1234567890"
        self.user.save()

        self.specialist = Specialist.objects.create(
            user=self.user,
            license_number="LIC12345",
            specialization="psychologist",
            qualifications="PhD in Psychology",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
            bio="Experienced specialist",
        )

        # Add service
        service = Service.objects.create(
            name="Consultation",
            category="mental_health",
            duration_minutes=60,
            base_price=Decimal("100.00"),
        )
        SpecialistService.objects.create(
            specialist=self.specialist,
            service=service,
            is_available=True,
        )

        # Add availability
        Availability.objects.create(
            specialist=self.specialist,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_recurring=True,
            valid_from=date(2026, 2, 1),
        )

    def test_serialize_specialist_detail(self):
        """Test serializing specialist detail"""
        serializer = SpecialistDetailSerializer(self.specialist)
        data = serializer.data

        self.assertEqual(data["id"], self.specialist.id)
        self.assertIn("user_info", data)
        self.assertIn("services", data)
        self.assertIn("availability", data)

    def test_get_user_info(self):
        """Test get_user_info method"""
        serializer = SpecialistDetailSerializer(self.specialist)
        user_info = serializer.data["user_info"]

        self.assertEqual(user_info["full_name"], "John Doe")
        self.assertEqual(user_info["email"], "specialist@test.com")
        self.assertEqual(user_info["phone"], "1234567890")

    def test_get_services(self):
        """Test get_services method"""
        serializer = SpecialistDetailSerializer(self.specialist)
        services = serializer.data["services"]

        self.assertEqual(len(services), 1)
        self.assertIn("service_details", services[0])

    def test_get_availability(self):
        """Test get_availability method"""
        serializer = SpecialistDetailSerializer(self.specialist)
        availability = serializer.data["availability"]

        self.assertEqual(len(availability), 1)
        self.assertEqual(availability[0]["day_of_week"], 1)


class SpecialistCreateSerializerTest(TestCase):
    """Test cases for SpecialistCreateSerializer"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="newspecialist@test.com",
            password="testpass123",
            user_type="specialist",
        )

    def test_create_specialist_success(self):
        """Test creating a specialist successfully"""
        data = {
            "user_id": self.user.id,
            "license_number": "LIC99999",
            "specialization": "psychiatrist",
            "qualifications": "MD, Board Certified",
            "years_experience": 10,
            "consultation_fee": "200.00",
            "bio": "Experienced psychiatrist",
        }

        serializer = SpecialistCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        specialist = serializer.save()

        self.assertEqual(specialist.user, self.user)
        self.assertEqual(specialist.license_number, "LIC99999")
        self.assertEqual(specialist.years_experience, 10)

    def test_create_with_user_info_update(self):
        """Test creating specialist with user info updates"""
        data = {
            "user_id": self.user.id,
            "email": "updated@test.com",
            "first_name": "Updated",
            "last_name": "Name",
            "phone": "9876543210",
            "license_number": "LIC99999",
            "specialization": "psychiatrist",
            "years_experience": 10,
            "consultation_fee": "200.00",
        }

        serializer = SpecialistCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        specialist = serializer.save()

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "updated@test.com")
        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(self.user.last_name, "Name")
        self.assertEqual(self.user.phone, "9876543210")

    def test_validate_user_not_found(self):
        """Test validation when user doesn't exist"""
        data = {
            "user_id": 99999,  # Non-existent
            "license_number": "LIC99999",
            "specialization": "psychiatrist",
            "years_experience": 10,
            "consultation_fee": "200.00",
        }

        serializer = SpecialistCreateSerializer(data=data)
        with self.assertRaises(NotFoundError):
            serializer.is_valid(raise_exception=True)

    def test_validate_user_already_specialist(self):
        """Test validation when user already has specialist profile"""
        Specialist.objects.create(
            user=self.user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
        )

        data = {
            "user_id": self.user.id,
            "license_number": "LIC99999",
            "specialization": "psychiatrist",
            "years_experience": 10,
            "consultation_fee": "200.00",
        }

        serializer = SpecialistCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("User already has a specialist profile", str(serializer.errors))

    def test_validate_duplicate_license_number(self):
        """Test validation for duplicate license number"""
        user2 = User.objects.create_user(
            email="other@test.com",
            password="testpass123",
            user_type="specialist",
        )
        Specialist.objects.create(
            user=user2,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
        )

        data = {
            "user_id": self.user.id,
            "license_number": "LIC12345",  # Duplicate
            "specialization": "psychiatrist",
            "years_experience": 10,
            "consultation_fee": "200.00",
        }

        serializer = SpecialistCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        # Model's unique constraint triggers, not custom validation
        self.assertIn("license_number", serializer.errors)

    def test_validate_negative_years_experience(self):
        """Test validation for negative years experience"""
        data = {
            "user_id": self.user.id,
            "license_number": "LIC99999",
            "specialization": "psychiatrist",
            "years_experience": -5,  # Invalid
            "consultation_fee": "200.00",
        }

        serializer = SpecialistCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        # Model's MinValueValidator triggers before custom validation
        self.assertIn("years_experience", serializer.errors)

    def test_validate_negative_consultation_fee(self):
        """Test validation for negative consultation fee"""
        data = {
            "user_id": self.user.id,
            "license_number": "LIC99999",
            "specialization": "psychiatrist",
            "years_experience": 10,
            "consultation_fee": "-50.00",  # Invalid
        }

        serializer = SpecialistCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        # Model's MinValueValidator triggers before custom validation
        self.assertIn("consultation_fee", serializer.errors)


class SpecialistUpdateSerializerTest(TestCase):
    """Test cases for SpecialistUpdateSerializer"""

    def setUp(self):
        """Set up test data"""
        user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            user_type="specialist",
        )
        self.specialist = Specialist.objects.create(
            user=user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
        )

    def test_update_specialist_success(self):
        """Test updating specialist successfully"""
        data = {
            "years_experience": 8,
            "consultation_fee": "180.00",
            "bio": "Updated bio",
        }

        serializer = SpecialistUpdateSerializer(
            self.specialist, data=data, partial=True
        )
        self.assertTrue(serializer.is_valid())
        updated_specialist = serializer.save()

        self.assertEqual(updated_specialist.years_experience, 8)
        self.assertEqual(updated_specialist.consultation_fee, Decimal("180.00"))
        self.assertEqual(updated_specialist.bio, "Updated bio")

    def test_validate_duplicate_license_on_update(self):
        """Test validation for duplicate license on update"""
        user2 = User.objects.create_user(
            email="other@test.com",
            password="testpass123",
            user_type="specialist",
        )
        Specialist.objects.create(
            user=user2,
            license_number="LIC99999",
            specialization="psychiatrist",
            years_experience=10,
            consultation_fee=Decimal("200.00"),
        )

        data = {"license_number": "LIC99999"}  # Duplicate

        serializer = SpecialistUpdateSerializer(
            self.specialist, data=data, partial=True
        )
        # Model's unique constraint or field-level validator triggers
        self.assertIn("license_number", serializer.errors)
        self.assertIn("License number already registered", str(serializer.errors))

    def test_validate_negative_values_on_update(self):
        """Test validation for negative values on update"""
        # Negative years_experience
        data = {"years_experience": -1}
        serializer = SpecialistUpdateSerializer(
            self.specialist, data=data, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("years_experience", serializer.errors)

        # Negative consultation_fee
        data = {"consultation_fee": "-50.00"}
        serializer = SpecialistUpdateSerializer(
            self.specialist, data=data, partial=True
        )
        self.assertFalse(serializer.is_valid())
        # Model's MinValueValidator triggers before custom validation
        self.assertIn("consultation_fee", serializer.errors)
        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "Ensure this value is greater than or equal to 0", str(serializer.errors)
        )


class SpecialistSearchSerializerTest(TestCase):
    """Test cases for SpecialistSearchSerializer"""

    def test_valid_search_params(self):
        """Test valid search parameters"""
        data = {
            "specialization": "psychologist",
            "min_rating": "4.0",
            "max_fee": "200.00",
            "accepting_new_patients": True,
            "service_id": 1,
            "search": "john",
            "ordering": "-rating",
            "page": 1,
            "page_size": 20,
        }

        serializer = SpecialistSearchSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_default_values(self):
        """Test default values for search"""
        data = {}

        serializer = SpecialistSearchSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["ordering"], "rating")
        self.assertEqual(serializer.validated_data["page"], 1)
        self.assertEqual(serializer.validated_data["page_size"], 20)

    def test_invalid_rating_range(self):
        """Test invalid rating range"""
        data = {"min_rating": "6.0"}  # Above maximum

        serializer = SpecialistSearchSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("min_rating", serializer.errors)

    def test_page_size_constraints(self):
        """Test page size constraints"""
        # Too large
        data = {"page_size": 150}
        serializer = SpecialistSearchSerializer(data=data)
        self.assertFalse(serializer.is_valid())

        # Valid max
        data = {"page_size": 100}
        serializer = SpecialistSearchSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class SpecialistServiceSerializerTest(TestCase):
    """Test cases for SpecialistServiceSerializer"""

    def setUp(self):
        """Set up test data"""
        user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            user_type="specialist",
        )
        self.specialist = Specialist.objects.create(
            user=user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
        )
        self.service = Service.objects.create(
            name="Consultation",
            category="mental_health",
            duration_minutes=60,
            base_price=Decimal("100.00"),
        )
        self.specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
            price_override=Decimal("120.00"),
            is_available=True,
        )

    def test_serialize_specialist_service(self):
        """Test serializing specialist service"""
        serializer = SpecialistServiceSerializer(self.specialist_service)
        data = serializer.data

        self.assertEqual(data["id"], self.specialist_service.id)
        self.assertEqual(data["service"], self.service.id)
        self.assertIn("service_details", data)
        self.assertEqual(Decimal(data["price_override"]), Decimal("120.00"))
        self.assertEqual(Decimal(data["effective_price"]), Decimal("120.00"))
        self.assertTrue(data["is_available"])

    def test_get_effective_price_with_override(self):
        """Test effective price with override"""
        serializer = SpecialistServiceSerializer(self.specialist_service)
        self.assertEqual(Decimal(serializer.data["effective_price"]), Decimal("120.00"))

    def test_get_effective_price_without_override(self):
        """Test effective price without override"""
        self.specialist_service.price_override = None
        self.specialist_service.save()

        serializer = SpecialistServiceSerializer(self.specialist_service)
        self.assertEqual(Decimal(serializer.data["effective_price"]), Decimal("100.00"))


class SpecialistServiceCreateSerializerTest(TestCase):
    """Test cases for SpecialistServiceCreateSerializer"""

    def setUp(self):
        """Set up test data"""
        user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            user_type="specialist",
        )
        self.specialist = Specialist.objects.create(
            user=user,
            license_number="LIC12345",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("150.00"),
        )
        self.service = Service.objects.create(
            name="Consultation",
            category="mental_health",
            duration_minutes=60,
            base_price=Decimal("100.00"),
            is_active=True,
        )

    def test_create_specialist_service_success(self):
        """Test creating specialist service successfully"""
        data = {
            "service_id": self.service.id,
            "price_override": "120.00",
        }

        context = {"specialist_id": self.specialist.id, "request": True}
        serializer = SpecialistServiceCreateSerializer(data=data, context=context)
        self.assertTrue(serializer.is_valid())

    def test_validate_service_not_found(self):
        """Test validation when service not found"""
        data = {
            "service_id": 99999,  # Non-existent
            "price_override": "120.00",
        }

        context = {"specialist_id": self.specialist.id, "request": True}
        serializer = SpecialistServiceCreateSerializer(data=data, context=context)

        with self.assertRaises(NotFoundError):
            serializer.is_valid(raise_exception=True)

    def test_validate_inactive_service(self):
        """Test validation for inactive service"""
        self.service.is_active = False
        self.service.save()

        data = {
            "service_id": self.service.id,
            "price_override": "120.00",
        }

        context = {"specialist_id": self.specialist.id, "request": True}
        serializer = SpecialistServiceCreateSerializer(data=data, context=context)

        with self.assertRaises(NotFoundError):
            serializer.is_valid(raise_exception=True)

    def test_validate_duplicate_service(self):
        """Test validation for duplicate service"""
        SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
        )

        data = {
            "service_id": self.service.id,
            "price_override": "120.00",
        }

        context = {"specialist_id": self.specialist.id, "request": True}
        serializer = SpecialistServiceCreateSerializer(data=data, context=context)

        self.assertFalse(serializer.is_valid())
        self.assertIn("Specialist already offers this service", str(serializer.errors))

    def test_validate_excessive_price_override(self):
        """Test validation for excessive price override"""
        data = {
            "service_id": self.service.id,
            "price_override": "350.00",  # More than 3x base price
        }

        context = {"specialist_id": self.specialist.id, "request": True}
        serializer = SpecialistServiceCreateSerializer(data=data, context=context)

        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "Price override cannot exceed 3 times the base price",
            str(serializer.errors),
        )

    def test_validate_without_context(self):
        """Test validation without context (should pass validation)"""
        data = {
            "service_id": self.service.id,
            "price_override": "120.00",
        }

        serializer = SpecialistServiceCreateSerializer(data=data)
        # Should not raise error when context is missing
        self.assertTrue(serializer.is_valid())

    def test_null_price_override_allowed(self):
        """Test that null price override is allowed"""
        data = {
            "service_id": self.service.id,
            "price_override": None,
        }

        context = {"specialist_id": self.specialist.id, "request": True}
        serializer = SpecialistServiceCreateSerializer(data=data, context=context)
        self.assertTrue(serializer.is_valid())
