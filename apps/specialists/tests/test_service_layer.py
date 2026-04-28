from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from apps.specialists.models import Specialist, Service, SpecialistService, Availability
from apps.specialists.services import CompanyServicesUseCases
from apps.core.exceptions.base_exceptions import (
    NotFoundError,
    ValidationError,
    ConflictError,
    BusinessRuleError,
)
from apps.specialists.services.specialist_use_cases import SpecialistsUseCases

User = get_user_model()


class CompanyServicesUseCasesTest(TestCase):
    """Test cases for CompanyServicesUseCases"""

    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Specialist",
        )

        # Create test specialist
        self.specialist = Specialist.objects.create(
            user=self.user,
            license_number="LIC123456",
            specialization="psychologist",
            qualifications="PhD in Psychology",
            years_experience=5,
            consultation_fee=Decimal("100.00"),
            is_accepting_new_patients=True,
            is_active=True,
        )

        # Create test service
        self.service = Service.objects.create(
            name="Individual Therapy",
            description="One-on-one therapy session",
            category="therapy",
            duration_minutes=60,
            base_price=Decimal("120.00"),
            is_active=True,
        )

    # ============= Service Name Validation Tests =============

    def test_validate_service_name_success(self):
        """Test valid service name validation"""
        name = "Valid Service Name"
        result = CompanyServicesUseCases.validate_service_name(name)
        self.assertEqual(result, "Valid Service Name")

    def test_validate_service_name_strips_whitespace(self):
        """Test service name whitespace stripping"""
        name = "  Service Name  "
        result = CompanyServicesUseCases.validate_service_name(name)
        self.assertEqual(result, "Service Name")

    def test_validate_service_name_too_short(self):
        """Test service name too short"""
        with self.assertRaises(ValidationError) as context:
            CompanyServicesUseCases.validate_service_name("AB")
        self.assertIn("at least 3 characters", str(context.exception))

    def test_validate_service_name_empty(self):
        """Test empty service name"""
        with self.assertRaises(ValidationError):
            CompanyServicesUseCases.validate_service_name("")

    def test_validate_service_name_whitespace_only(self):
        """Test whitespace-only service name"""
        with self.assertRaises(ValidationError):
            CompanyServicesUseCases.validate_service_name("  ")

    # ============= Service Duration Validation Tests =============

    def test_validate_service_duration_success(self):
        """Test valid service duration"""
        durations = [15, 30, 45, 60, 90, 120]
        for duration in durations:
            result = CompanyServicesUseCases.validate_service_duration(duration)
            self.assertEqual(result, duration)

    def test_validate_service_duration_too_short(self):
        """Test service duration too short"""
        with self.assertRaises(ValidationError) as context:
            CompanyServicesUseCases.validate_service_duration(3)
        self.assertIn("at least", str(context.exception))

    def test_validate_service_duration_too_long(self):
        """Test service duration too long"""
        with self.assertRaises(ValidationError) as context:
            CompanyServicesUseCases.validate_service_duration(500)
        self.assertIn("cannot exceed", str(context.exception))

    def test_validate_service_duration_not_15_minute_increment(self):
        """Test service duration not in 15-minute increments"""
        with self.assertRaises(ValidationError) as context:
            CompanyServicesUseCases.validate_service_duration(25)
        self.assertIn("15-minute increments", str(context.exception))

    # ============= Service Price Validation Tests =============

    def test_validate_service_price_success(self):
        """Test valid service price"""
        prices = [Decimal("10.00"), Decimal("50.00"), Decimal("100.00")]
        for price in prices:
            result = CompanyServicesUseCases.validate_service_price(price)
            self.assertEqual(result, price)

    def test_validate_service_price_too_low(self):
        """Test service price too low"""
        with self.assertRaises(ValidationError) as context:
            CompanyServicesUseCases.validate_service_price(Decimal("3.00"))
        self.assertIn("cannot be less than", str(context.exception))

    def test_validate_service_price_too_high(self):
        """Test service price too high"""
        with self.assertRaises(ValidationError) as context:
            CompanyServicesUseCases.validate_service_price(Decimal("6000.00"))
        self.assertIn("cannot exceed", str(context.exception))

    def test_validate_service_price_high_not_in_100_increments(self):
        """Test high service price not in $100 increments"""
        with self.assertRaises(ValidationError) as context:
            CompanyServicesUseCases.validate_service_price(Decimal("1050.00"))
        self.assertIn("$100 increments", str(context.exception))

    def test_validate_service_price_high_in_100_increments(self):
        """Test high service price in $100 increments"""
        result = CompanyServicesUseCases.validate_service_price(Decimal("1100.00"))
        self.assertEqual(result, Decimal("1100.00"))

    # ============= Service Category Validation Tests =============

    def test_validate_service_category_success(self):
        """Test valid service category"""
        for category, _ in Service.CATEGORY_CHOICES:
            result = CompanyServicesUseCases.validate_service_category(category)
            self.assertEqual(result, category)

    def test_validate_service_category_invalid(self):
        """Test invalid service category"""
        with self.assertRaises(ValidationError) as context:
            CompanyServicesUseCases.validate_service_category("invalid_category")
        self.assertIn("Invalid service category", str(context.exception))

    # ============= Service Creation Tests =============

    def test_create_service_success(self):
        """Test successful service creation"""
        service_data = {
            "name": "Group Therapy",
            "category": "therapy",
            "duration_minutes": 90,
            "base_price": Decimal("150.00"),
            "description": "Group therapy session",
        }

        service = CompanyServicesUseCases.create_service(**service_data)

        self.assertIsNotNone(service.id)
        self.assertEqual(service.name, "Group Therapy")
        self.assertEqual(service.category, "therapy")
        self.assertEqual(service.duration_minutes, 90)
        self.assertEqual(service.base_price, Decimal("150.00"))
        self.assertTrue(service.is_active)

    def test_create_service_duplicate_name_in_category(self):
        """Test creating service with duplicate name in same category"""
        service_data = {
            "name": "Individual Therapy",
            "category": "therapy",
            "duration_minutes": 60,
            "base_price": Decimal("120.00"),
        }

        with self.assertRaises(ConflictError) as context:
            CompanyServicesUseCases.create_service(**service_data)
        self.assertIn("already exists", str(context.exception))

    def test_create_service_same_name_different_category(self):
        """Test creating service with same name in different category"""
        service_data = {
            "name": "Individual Therapy",
            "category": "wellness",
            "duration_minutes": 60,
            "base_price": Decimal("80.00"),
        }

        service = CompanyServicesUseCases.create_service(**service_data)
        self.assertIsNotNone(service.id)
        self.assertEqual(service.category, "wellness")

    def test_create_service_invalid_duration(self):
        """Test creating service with invalid duration"""
        service_data = {
            "name": "Test Service",
            "category": "therapy",
            "duration_minutes": 25,  # Not 15-minute increment
            "base_price": Decimal("100.00"),
        }

        with self.assertRaises(ValidationError):
            CompanyServicesUseCases.create_service(**service_data)

    def test_create_service_invalid_price(self):
        """Test creating service with invalid price"""
        service_data = {
            "name": "Test Service",
            "category": "therapy",
            "duration_minutes": 60,
            "base_price": Decimal("2.00"),  # Too low
        }

        with self.assertRaises(ValidationError):
            CompanyServicesUseCases.create_service(**service_data)

    # ============= Service Update Tests =============

    def test_update_service_name_success(self):
        """Test successful service name update"""
        updated_service = CompanyServicesUseCases.update_service(
            self.service, name="Updated Therapy Session"
        )

        self.assertEqual(updated_service.name, "Updated Therapy Session")

    def test_update_service_price_success(self):
        """Test successful service price update"""
        new_price = Decimal("150.00")
        updated_service = CompanyServicesUseCases.update_service(
            self.service, base_price=new_price
        )

        self.assertEqual(updated_service.base_price, new_price)

    def test_update_service_duration_success(self):
        """Test successful service duration update"""
        updated_service = CompanyServicesUseCases.update_service(
            self.service, duration_minutes=90
        )

        self.assertEqual(updated_service.duration_minutes, 90)

    def test_update_service_to_duplicate_name_in_category(self):
        """Test updating service to duplicate name in same category"""
        # Create another service
        Service.objects.create(
            name="Existing Service",
            category="therapy",
            duration_minutes=60,
            base_price=Decimal("100.00"),
        )

        with self.assertRaises(ConflictError):
            CompanyServicesUseCases.update_service(
                self.service, name="Existing Service", category="therapy"
            )

    def test_update_service_invalid_duration(self):
        """Test updating service with invalid duration"""
        with self.assertRaises(ValidationError):
            CompanyServicesUseCases.update_service(self.service, duration_minutes=25)

    def test_update_service_invalid_price(self):
        """Test updating service with invalid price"""
        with self.assertRaises(ValidationError):
            CompanyServicesUseCases.update_service(
                self.service, base_price=Decimal("10000.00")
            )

    # ============= Service Deactivation Tests =============

    def test_deactivate_service_success(self):
        """Test successful service deactivation"""
        result = CompanyServicesUseCases.deactivate_service(self.service)

        self.assertFalse(result.is_active)

    def test_deactivate_service_with_no_upcoming_specialist(self):
        """Test deactivating service with no upcoming appointments"""
        # Add service to specialist
        SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
            is_available=True,
        )

        with self.assertRaises(ConflictError) as context:
            CompanyServicesUseCases.deactivate_service(self.service)

    # ============= Service Reactivation Tests =============

    def test_reactivate_service_success(self):
        """Test successful service reactivation"""
        self.service.is_active = False
        self.service.save()

        result = CompanyServicesUseCases.reactivate_service(self.service)
        self.assertTrue(result.is_active)

    # ============= Get Services By Category Tests =============

    def test_get_services_by_category_all(self):
        """Test getting all services"""
        services = CompanyServicesUseCases.get_services_by_category()
        self.assertGreater(len(services), 0)
        self.assertTrue(all(s is not None for s in services.keys()))

    def test_get_services_by_category_filtered(self):
        """Test getting services filtered by category"""
        services = CompanyServicesUseCases.get_services_by_category(category="therapy")
        self.assertGreater(len(services), 0)
        self.assertTrue(all(s == "therapy" for s in services.keys()))

    def test_get_services_by_category_include_inactive(self):
        """Test getting services including inactive ones"""
        # Deactivate a service
        self.service.is_active = False
        self.service.save()

        # Get categories with inactive services
        result_inactive = CompanyServicesUseCases.get_services_by_category(
            active_only=False
        )

        # Verify the result is a dictionary with category data
        self.assertIsInstance(result_inactive, dict)
        self.assertIn("therapy", result_inactive)

        # Get only active services for comparison
        result_active = CompanyServicesUseCases.get_services_by_category(
            active_only=True
        )

        # When active_only=False, categories should be in result even if all services deactivated
        # This verifies the method processes the query correctly
        self.assertIsInstance(result_active, dict)

    # ============= Service Statistics Tests =============

    def test_get_service_statistics(self):
        """Test getting service statistics"""
        stats = CompanyServicesUseCases.get_service_statistics()

        self.assertIn("summary", stats)
        self.assertIn("category_distribution", stats)
        self.assertIn("popular_services", stats)
        self.assertIn("averages", stats)
        self.assertGreater(stats["summary"]["total_services"], 0)

    def test_get_service_statistics_with_inactive(self):
        """Test getting service statistics including inactive services"""
        # Deactivate service
        self.service.is_active = False
        self.service.save()

        stats = CompanyServicesUseCases.get_service_statistics(include_inactive=True)
        self.assertGreaterEqual(stats["summary"]["total_inactive"], 1)

    # ============= Add Service To Specialist Tests =============

    def test_add_service_to_specialist_success(self):
        """Test successfully adding service to specialist"""
        result = SpecialistsUseCases.add_service_to_specialist(
            self.service, self.specialist
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.service, self.service)
        self.assertEqual(result.specialist, self.specialist)
        self.assertTrue(result.is_available)
        self.assertIsNone(result.price_override)

    def test_add_service_to_specialist_with_price_override(self):
        """Test adding service with price override"""
        price_override = Decimal("100.00")
        result = SpecialistsUseCases.add_service_to_specialist(
            service_id=self.service.id,
            specialist=self.specialist,
            price_override=price_override,
        )

        self.assertEqual(result.price_override, price_override)

    def test_add_service_to_specialist_inactive_service(self):
        """Test adding inactive service to specialist"""
        self.service.is_active = False
        self.service.save()

        with self.assertRaises(NotFoundError) as context:
            SpecialistsUseCases.add_service_to_specialist(
                service_id=self.service.id, specialist=self.specialist
            )
        self.assertIn("not found or inactive", str(context.exception))

    def test_add_service_to_specialist_inactive_specialist(self):
        """Test adding service to inactive specialist"""
        self.specialist.is_active = False
        self.specialist.save()

        with self.assertRaises(BusinessRuleError) as context:
            SpecialistsUseCases.add_service_to_specialist(
                service_id=self.service.id, specialist=self.specialist
            )
        self.assertIn("inactive specialist", str(context.exception))

    def test_add_service_to_specialist_duplicate(self):
        """Test adding duplicate service to specialist"""
        SpecialistsUseCases.add_service_to_specialist(
            service_id=self.service.id, specialist=self.specialist
        )

        with self.assertRaises(ConflictError) as context:
            SpecialistsUseCases.add_service_to_specialist(
                service_id=self.service.id, specialist=self.specialist
            )
        self.assertIn("already offers", str(context.exception))

    def test_add_service_to_specialist_price_override_negative(self):
        """Test adding service with negative price override"""
        with self.assertRaises(ValidationError) as context:
            SpecialistsUseCases.add_service_to_specialist(
                service_id=self.service.id,
                specialist=self.specialist,
                price_override=Decimal("-10.00"),
            )
        self.assertIn("cannot be negative", str(context.exception))

    def test_add_service_to_specialist_price_override_too_high(self):
        """Test adding service with price override too high"""
        with self.assertRaises(BusinessRuleError) as context:
            SpecialistsUseCases.add_service_to_specialist(
                service_id=self.service.id,
                specialist=self.specialist,
                price_override=self.service.base_price * 4,
            )
        self.assertIn("3 times", str(context.exception))

    def test_add_service_to_specialist_price_override_too_low(self):
        """Test adding service with price override too low"""
        with self.assertRaises(BusinessRuleError) as context:
            SpecialistsUseCases.add_service_to_specialist(
                service_id=self.service.id,
                specialist=self.specialist,
                price_override=self.service.base_price * Decimal("0.3"),
            )
        self.assertIn("50%", str(context.exception))

    # ============= Remove Service From Specialist Tests =============

    def test_remove_service_from_specialist_success(self):
        """Test successfully removing service from specialist"""
        specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
            is_available=True,
        )

        result = SpecialistsUseCases.remove_service_from_specialist(
            specialist=self.specialist, service_id=self.service.id
        )
        self.assertTrue(result)

    # ============= Update Service Price For Specialist Tests =============

    def test_update_service_price_for_specialist_success(self):
        """Test successfully updating service price for specialist"""
        specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
            price_override=Decimal("100.00"),
        )

        new_price = Decimal("130.00")
        result = CompanyServicesUseCases.update_service_price_for_specialist(
            specialist_service, new_price
        )

        self.assertEqual(result.price_override, new_price)

    def test_update_service_price_for_specialist_negative(self):
        """Test updating service price with negative value"""
        specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
            price_override=Decimal("100.00"),
        )

        with self.assertRaises(ValidationError) as context:
            CompanyServicesUseCases.update_service_price_for_specialist(
                specialist_service, Decimal("-10.00")
            )
        self.assertIn("cannot be negative", str(context.exception))

    def test_update_service_price_for_specialist_too_high(self):
        """Test updating service price too high"""
        specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
            price_override=Decimal("100.00"),
        )

        with self.assertRaises(ValidationError):
            CompanyServicesUseCases.update_service_price_for_specialist(
                specialist_service, self.service.base_price * 4
            )

    def test_update_service_price_for_specialist_too_low(self):
        """Test updating service price too low"""
        specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
            price_override=Decimal("100.00"),
        )

        with self.assertRaises(ValidationError):
            CompanyServicesUseCases.update_service_price_for_specialist(
                specialist_service, self.service.base_price * Decimal("0.3")
            )

    # ============= Get Services Grouped By Category Tests =============

    def test_get_services_grouped_by_category(self):
        """Test getting services grouped by category"""
        # Create services in different categories
        Service.objects.create(
            name="Mental Health Assessment",
            category="mental_health",
            duration_minutes=45,
            base_price=Decimal("80.00"),
        )

        result = CompanyServicesUseCases.get_services_grouped_by_category()

        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

        for category, data in result.items():
            self.assertIn("display_name", data)
            self.assertIn("count", data)
            self.assertIn("avg_duration", data)
            self.assertIn("avg_price", data)
            self.assertIn("price_range", data)
            self.assertIn("top_services", data)


class CompanyServicesUseCasesEdgeCasesTest(TestCase):
    """Test edge cases and boundary conditions"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="edge@test.com", password="testpass123"
        )
        self.specialist = Specialist.objects.create(
            user=self.user,
            license_number="EDGE123",
            specialization="therapist",
            years_experience=1,
            consultation_fee=Decimal("50.00"),
        )

    def test_service_name_exactly_3_characters(self):
        """Test service name with exactly 3 characters (boundary)"""
        result = CompanyServicesUseCases.validate_service_name("ABC")
        self.assertEqual(result, "ABC")

    def test_service_duration_minimum_boundary(self):
        """Test service duration at minimum boundary"""
        result = CompanyServicesUseCases.validate_service_duration(15)
        self.assertEqual(result, 15)

    def test_service_duration_maximum_boundary(self):
        """Test service duration at maximum boundary"""
        result = CompanyServicesUseCases.validate_service_duration(480)
        self.assertEqual(result, 480)

    def test_service_price_minimum_boundary(self):
        """Test service price at minimum boundary"""
        result = CompanyServicesUseCases.validate_service_price(Decimal("5.00"))
        self.assertEqual(result, Decimal("5.00"))

    def test_service_price_maximum_boundary(self):
        """Test service price at maximum boundary"""
        result = CompanyServicesUseCases.validate_service_price(Decimal("5000.00"))
        self.assertEqual(result, Decimal("5000.00"))

    def test_update_service_no_changes(self):
        """Test updating service with no actual changes"""
        service = Service.objects.create(
            name="Test Service",
            category="therapy",
            duration_minutes=60,
            base_price=Decimal("100.00"),
        )

        # Update with same values
        result = CompanyServicesUseCases.update_service(
            service,
            name="Test Service",
            duration_minutes=60,
            base_price=Decimal("100.00"),
        )

        self.assertEqual(result.name, "Test Service")

    def test_price_override_at_50_percent(self):
        """Test price override at exactly 50% (boundary)"""
        service = Service.objects.create(
            name="Test",
            category="therapy",
            duration_minutes=60,
            base_price=Decimal("100.00"),
        )

        price_override = service.base_price * Decimal("0.5")
        result = SpecialistsUseCases.add_service_to_specialist(
            service, self.specialist, price_override=price_override
        )

        self.assertEqual(result.price_override, Decimal("50.00"))

    def test_price_override_at_3x(self):
        """Test price override at exactly 3x (boundary)"""
        service = Service.objects.create(
            name="Test",
            category="therapy",
            duration_minutes=60,
            base_price=Decimal("100.00"),
        )

        price_override = service.base_price * 3
        result = SpecialistsUseCases.add_service_to_specialist(
            service, self.specialist, price_override=price_override
        )

        self.assertEqual(result.price_override, Decimal("300.00"))
