from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, time, date
from decimal import Decimal

from apps.specialists.models import Specialist, Service, SpecialistService, Availability
from apps.appointments.models import Appointment
from apps.specialists.services.specialist_service import SpecialistServiceLayer
from apps.core.exceptions.base_exceptions import (
    ValidationError,
    NotFoundError,
    BusinessRuleError,
)

User = get_user_model()


class SpecialistServiceLayerTest(TestCase):
    """Test cases for SpecialistServiceLayer"""

    def setUp(self):
        """Set up test data"""
        # Create test users
        self.user1 = User.objects.create_user(
            email="spec1@test.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
        )

        self.user2 = User.objects.create_user(
            email="spec2@test.com",
            password="testpass123",
            first_name="Jane",
            last_name="Smith",
        )

        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Patient",
        )

        # Create test specialist
        self.specialist = Specialist.objects.create(
            user=self.user1,
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
            category="therapy",
            duration_minutes=60,
            base_price=Decimal("120.00"),
            is_active=True,
        )

    # ============= License Number Validation Tests =============

    def test_validate_license_number_success(self):
        """Test valid license number validation"""
        license_number = "ABC123XYZ"
        result = SpecialistServiceLayer.validate_license_number(license_number)
        self.assertEqual(result, "ABC123XYZ")

    def test_validate_license_number_strips_whitespace(self):
        """Test license number whitespace stripping"""
        license_number = "  ABC123  "
        result = SpecialistServiceLayer.validate_license_number(license_number)
        self.assertEqual(result, "ABC123")

    def test_validate_license_number_too_short(self):
        """Test license number too short"""
        with self.assertRaises(ValidationError) as context:
            SpecialistServiceLayer.validate_license_number("AB")
        self.assertIn("between 3 and 30 characters", str(context.exception))

    def test_validate_license_number_too_long(self):
        """Test license number too long"""
        with self.assertRaises(ValidationError):
            SpecialistServiceLayer.validate_license_number("A" * 31)

    def test_validate_license_number_duplicate(self):
        """Test duplicate license number"""
        with self.assertRaises(ValidationError) as context:
            SpecialistServiceLayer.validate_license_number("LIC123456")
        self.assertIn("already registered", str(context.exception))

    def test_validate_license_number_exclude_specialist(self):
        """Test license number validation excluding current specialist"""
        result = SpecialistServiceLayer.validate_license_number(
            "LIC123456", exclude_specialist_id=self.specialist.id
        )
        self.assertEqual(result, "LIC123456")

    # ============= Years Experience Validation Tests =============

    def test_validate_years_experience_success(self):
        """Test valid years experience"""
        years = [0, 1, 5, 10, 30, 60]
        for year in years:
            result = SpecialistServiceLayer.validate_years_experience(year)
            self.assertEqual(result, year)

    def test_validate_years_experience_negative(self):
        """Test negative years experience"""
        with self.assertRaises(ValidationError) as context:
            SpecialistServiceLayer.validate_years_experience(-1)
        self.assertIn("cannot be less than", str(context.exception))

    def test_validate_years_experience_too_high(self):
        """Test years experience too high"""
        with self.assertRaises(ValidationError) as context:
            SpecialistServiceLayer.validate_years_experience(65)
        self.assertIn("cannot exceed", str(context.exception))

    # ============= Consultation Fee Validation Tests =============

    def test_validate_consultation_fee_success(self):
        """Test valid consultation fee"""
        fees = [Decimal("10.00"), Decimal("50.00"), Decimal("500.00")]
        for fee in fees:
            result = SpecialistServiceLayer.validate_consultation_fee(fee)
            self.assertEqual(result, fee)

    def test_validate_consultation_fee_too_low(self):
        """Test consultation fee too low"""
        with self.assertRaises(ValidationError) as context:
            SpecialistServiceLayer.validate_consultation_fee(Decimal("5.00"))
        self.assertIn("cannot be less than", str(context.exception))

    def test_validate_consultation_fee_too_high(self):
        """Test consultation fee too high"""
        with self.assertRaises(ValidationError) as context:
            SpecialistServiceLayer.validate_consultation_fee(Decimal("1500.00"))
        self.assertIn("cannot exceed", str(context.exception))

    # ============= Rating Validation Tests =============

    def test_validate_rating_success(self):
        """Test valid rating"""
        ratings = [Decimal("0.00"), Decimal("2.50"), Decimal("5.00")]
        for rating in ratings:
            result = SpecialistServiceLayer.validate_rating(rating)
            self.assertEqual(result, rating)

    def test_validate_rating_negative(self):
        """Test negative rating"""
        with self.assertRaises(ValidationError) as context:
            SpecialistServiceLayer.validate_rating(Decimal("-1.00"))
        self.assertIn("cannot be less than", str(context.exception))

    def test_validate_rating_too_high(self):
        """Test rating too high"""
        with self.assertRaises(ValidationError) as context:
            SpecialistServiceLayer.validate_rating(Decimal("6.00"))
        self.assertIn("cannot exceed", str(context.exception))

    # ============= Specialist Creation Tests =============

    def test_create_specialist_success(self):
        """Test successful specialist creation"""
        specialist_data = {
            "user_id": self.user2.id,
            "license_number": "NEW123456",
            "specialization": "psychiatrist",
            "qualifications": "MD in Psychiatry",
            "years_experience": 8,
            "consultation_fee": Decimal("150.00"),
            "bio": "Experienced psychiatrist",
            "rating": Decimal("4.50"),
        }

        specialist = SpecialistServiceLayer.create_specialist(**specialist_data)

        self.assertIsNotNone(specialist.id)
        self.assertEqual(specialist.license_number, "NEW123456")
        self.assertEqual(specialist.specialization, "psychiatrist")
        self.assertEqual(specialist.years_experience, 8)
        self.assertEqual(specialist.consultation_fee, Decimal("150.00"))
        self.assertTrue(specialist.is_active)

    def test_create_specialist_invalid_license(self):
        """Test creating specialist with invalid license"""
        specialist_data = {
            "user_id": self.user2.id,
            "license_number": "AB",  # Too short
            "specialization": "psychiatrist",
            "years_experience": 5,
            "consultation_fee": Decimal("100.00"),
        }

        with self.assertRaises(ValidationError):
            SpecialistServiceLayer.create_specialist(**specialist_data)

    def test_create_specialist_invalid_years_experience(self):
        """Test creating specialist with invalid years experience"""
        specialist_data = {
            "user_id": self.user2.id,
            "license_number": "NEW123456",
            "specialization": "psychiatrist",
            "years_experience": -1,  # Negative
            "consultation_fee": Decimal("100.00"),
        }

        with self.assertRaises(ValidationError):
            SpecialistServiceLayer.create_specialist(**specialist_data)

    def test_create_specialist_invalid_consultation_fee(self):
        """Test creating specialist with invalid consultation fee"""
        specialist_data = {
            "user_id": self.user2.id,
            "license_number": "NEW123456",
            "specialization": "psychiatrist",
            "years_experience": 5,
            "consultation_fee": Decimal("5.00"),  # Too low
        }

        with self.assertRaises(ValidationError):
            SpecialistServiceLayer.create_specialist(**specialist_data)

    # ============= Specialist Update Tests =============

    def test_update_specialist_license_number(self):
        """Test updating specialist license number"""
        updated = SpecialistServiceLayer.update_specialist(
            self.specialist.id, license_number="UPDATED123"
        )

        self.assertEqual(updated.license_number, "UPDATED123")

    def test_update_specialist_years_experience(self):
        """Test updating specialist years experience"""
        updated = SpecialistServiceLayer.update_specialist(
            self.specialist.id, years_experience=10
        )

        self.assertEqual(updated.years_experience, 10)

    def test_update_specialist_consultation_fee(self):
        """Test updating specialist consultation fee"""
        updated = SpecialistServiceLayer.update_specialist(
            self.specialist.id, consultation_fee=Decimal("150.00")
        )

        self.assertEqual(updated.consultation_fee, Decimal("150.00"))

    def test_update_specialist_rating(self):
        """Test updating specialist rating"""
        updated = SpecialistServiceLayer.update_specialist(
            self.specialist.id, rating=Decimal("4.80")
        )

        self.assertEqual(updated.rating, Decimal("4.80"))

    def test_update_specialist_not_found(self):
        """Test updating non-existent specialist"""
        with self.assertRaises(NotFoundError):
            SpecialistServiceLayer.update_specialist(99999, rating=Decimal("4.50"))

    def test_update_specialist_invalid_license(self):
        """Test updating with invalid license number"""
        with self.assertRaises(ValidationError):
            SpecialistServiceLayer.update_specialist(
                self.specialist.id, license_number="AB"
            )

    # ============= Specialist Deletion Tests =============

    def test_delete_specialist_no_appointments(self):
        """Test deleting specialist with no appointments"""
        result = SpecialistServiceLayer.delete_specialist(
            self.specialist.id, deleted_by=self.user1
        )

        # Should be deactivated, not deleted
        self.assertFalse(result.is_active)
        self.assertFalse(result.is_accepting_new_patients)

    def test_delete_specialist_with_upcoming_appointments(self):
        """Test deleting specialist with upcoming appointments"""
        # Create upcoming appointment
        tomorrow = timezone.now() + timedelta(days=1)
        Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=tomorrow,
            start_time=tomorrow,
            end_time=tomorrow + timedelta(hours=1),
            duration_minutes=60,
            status="scheduled",
        )

        with self.assertRaises(BusinessRuleError) as context:
            SpecialistServiceLayer.delete_specialist(
                self.specialist.id, deleted_by=self.user1
            )
        self.assertIn("upcoming appointment", str(context.exception))

    def test_delete_specialist_not_found(self):
        """Test deleting non-existent specialist"""
        with self.assertRaises(NotFoundError):
            SpecialistServiceLayer.delete_specialist(99999, deleted_by=self.user1)

    # ============= Search Specialists Tests =============

    def test_search_specialists_no_filters(self):
        """Test searching specialists without filters"""
        specialists, pagination = SpecialistServiceLayer.search_specialists({})

        self.assertGreater(len(specialists), 0)
        self.assertIn("total", pagination)
        self.assertIn("page", pagination)
        self.assertEqual(pagination["page"], 1)

    def test_search_specialists_by_specialization(self):
        """Test searching specialists by specialization"""
        specialists, _ = SpecialistServiceLayer.search_specialists(
            {"specialization": "psychologist"}
        )

        self.assertGreater(len(specialists), 0)
        self.assertTrue(all(s.specialization == "psychologist" for s in specialists))

    def test_search_specialists_by_min_rating(self):
        """Test searching specialists by minimum rating"""
        specialists, _ = SpecialistServiceLayer.search_specialists(
            {"min_rating": Decimal("4.00")}
        )

        self.assertTrue(all(s.rating >= Decimal("4.00") for s in specialists))

    def test_search_specialists_by_max_fee(self):
        """Test searching specialists by maximum fee"""
        specialists, _ = SpecialistServiceLayer.search_specialists(
            {"max_fee": Decimal("150.00")}
        )

        self.assertTrue(
            all(s.consultation_fee <= Decimal("150.00") for s in specialists)
        )

    def test_search_specialists_accepting_new_patients(self):
        """Test searching specialists accepting new patients"""
        specialists, _ = SpecialistServiceLayer.search_specialists(
            {"accepting_new_patients": True}
        )

        self.assertTrue(all(s.is_accepting_new_patients for s in specialists))

    def test_search_specialists_by_search_term(self):
        """Test searching specialists by search term"""
        specialists, _ = SpecialistServiceLayer.search_specialists({"search": "John"})

        # Should find specialists with matching name
        self.assertGreater(len(specialists), 0)

    def test_search_specialists_pagination(self):
        """Test specialists search pagination"""
        # Create multiple specialists
        for i in range(5):
            user = User.objects.create_user(
                email=f"spec{i}@test.com",
                password="testpass123",
            )
            Specialist.objects.create(
                user=user,
                license_number=f"LIC{i}00000",
                specialization="therapist",
                years_experience=i + 1,
                consultation_fee=Decimal("80.00"),
            )

        specialists, pagination = SpecialistServiceLayer.search_specialists(
            {}, page=1, page_size=2
        )

        self.assertEqual(len(specialists), 2)
        self.assertEqual(pagination["page_size"], 2)
        self.assertTrue(pagination["has_next"])

    # ============= Get Specialist Detail Tests =============

    def test_get_specialist_detail_success(self):
        """Test getting specialist details"""
        result = SpecialistServiceLayer.get_specialist_detail(self.specialist.id)

        self.assertIn("specialist", result)
        self.assertIn("stats", result)
        self.assertEqual(result["specialist"].id, self.specialist.id)

    def test_get_specialist_detail_not_found(self):
        """Test getting details for non-existent specialist"""
        with self.assertRaises(NotFoundError):
            SpecialistServiceLayer.get_specialist_detail(99999)

    # ============= Get Specialist Statistics Tests =============

    def test_get_specialist_statistics(self):
        """Test getting specialist statistics"""
        stats = SpecialistServiceLayer.get_specialist_statistics(self.specialist.id)

        self.assertIn("total_appointments", stats)
        self.assertIn("recent_appointments", stats)
        self.assertIn("patient_count", stats)
        self.assertIn("avg_rating", stats)
        self.assertIn("todays_appointments", stats)
        self.assertIn("upcoming_appointments", stats)
        self.assertIn("cancellation_rate", stats)
        self.assertIn("total_revenue", stats)

    def test_get_specialist_statistics_with_appointments(self):
        """Test statistics with appointments"""
        # Create some appointments
        today = timezone.now()
        for i in range(3):
            Appointment.objects.create(
                patient=self.patient,
                specialist=self.specialist,
                appointment_type="consultation",
                appointment_date=today + timedelta(days=i),
                start_time=today + timedelta(days=i),
                end_time=today + timedelta(days=i, hours=1),
                duration_minutes=60,
                status="scheduled",
            )

        stats = SpecialistServiceLayer.get_specialist_statistics(self.specialist.id)

        self.assertGreaterEqual(stats["total_appointments"], 3)
        self.assertGreaterEqual(stats["upcoming_appointments"], 3)

    # ============= Add Service To Specialist Tests =============

    def test_add_service_to_specialist_success(self):
        """Test successfully adding service to specialist"""
        result = SpecialistServiceLayer.add_service_to_specialist(
            self.specialist.id, self.service.id
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.specialist, self.specialist)
        self.assertEqual(result.service, self.service)
        self.assertTrue(result.is_available)

    def test_add_service_to_specialist_with_price_override(self):
        """Test adding service with price override"""
        result = SpecialistServiceLayer.add_service_to_specialist(
            self.specialist.id, self.service.id, price_override=Decimal("100.00")
        )

        self.assertEqual(result.price_override, Decimal("100.00"))

    def test_add_service_to_specialist_not_found(self):
        """Test adding service to non-existent specialist"""
        with self.assertRaises(NotFoundError):
            SpecialistServiceLayer.add_service_to_specialist(99999, self.service.id)

    def test_add_service_to_specialist_service_not_found(self):
        """Test adding non-existent service to specialist"""
        with self.assertRaises(NotFoundError):
            SpecialistServiceLayer.add_service_to_specialist(self.specialist.id, 99999)

    def test_add_service_to_specialist_duplicate(self):
        """Test adding duplicate service"""
        SpecialistServiceLayer.add_service_to_specialist(
            self.specialist.id, self.service.id
        )

        with self.assertRaises(ValidationError) as context:
            SpecialistServiceLayer.add_service_to_specialist(
                self.specialist.id, self.service.id
            )
        self.assertIn("already offers", str(context.exception))

    def test_add_service_to_specialist_invalid_price_override(self):
        """Test adding service with invalid price override"""
        with self.assertRaises(ValidationError):
            SpecialistServiceLayer.add_service_to_specialist(
                self.specialist.id,
                self.service.id,
                price_override=self.service.base_price * 4,
            )

    # ============= Remove Service From Specialist Tests =============

    def test_remove_service_from_specialist_success(self):
        """Test successfully removing service from specialist"""
        SpecialistServiceLayer.add_service_to_specialist(
            self.specialist.id, self.service.id
        )

        result = SpecialistServiceLayer.remove_service_from_specialist(
            self.specialist.id, self.service.id
        )

        self.assertFalse(result.is_available)

    def test_remove_service_from_specialist_not_found(self):
        """Test removing non-existent service"""
        with self.assertRaises(NotFoundError):
            SpecialistServiceLayer.remove_service_from_specialist(
                self.specialist.id, self.service.id
            )

    # ============= Update Service Price Tests =============

    def test_update_service_price_success(self):
        """Test successfully updating service price"""
        SpecialistServiceLayer.add_service_to_specialist(
            self.specialist.id, self.service.id, price_override=Decimal("100.00")
        )

        result = SpecialistServiceLayer.update_service_price(
            self.specialist.id, self.service.id, Decimal("110.00")
        )

        self.assertEqual(result.price_override, Decimal("110.00"))

    def test_update_service_price_negative(self):
        """Test updating service price with negative value"""
        SpecialistServiceLayer.add_service_to_specialist(
            self.specialist.id, self.service.id
        )

        with self.assertRaises(ValidationError):
            SpecialistServiceLayer.update_service_price(
                self.specialist.id, self.service.id, Decimal("-10.00")
            )

    def test_update_service_price_too_high(self):
        """Test updating service price too high"""
        SpecialistServiceLayer.add_service_to_specialist(
            self.specialist.id, self.service.id
        )

        with self.assertRaises(ValidationError):
            SpecialistServiceLayer.update_service_price(
                self.specialist.id, self.service.id, self.service.base_price * 4
            )

    # ============= Get Specialists By Specialization Tests =============

    def test_get_specialists_by_specialization(self):
        """Test getting specialists grouped by specialization"""
        result = SpecialistServiceLayer.get_specialists_by_specialization()

        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

        for specialization, data in result.items():
            self.assertIn("display_name", data)
            self.assertIn("count", data)
            self.assertIn("avg_rating", data)
            self.assertIn("avg_fee", data)
            self.assertIn("top_specialists", data)

    # ============= Calculate Availability Percentage Tests =============

    def test_calculate_availability_percentage_no_availability(self):
        """Test calculating availability with no availability records"""
        result = SpecialistServiceLayer.calculate_availability_percentage(
            self.specialist.id
        )

        self.assertEqual(result, 0.0)

    def test_calculate_availability_percentage_with_availability(self):
        """Test calculating availability with availability records"""
        # Create availability
        Availability.objects.create(
            specialist=self.specialist,
            day_of_week=0,  # Monday
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_recurring=True,
            valid_from=date.today(),
            valid_until=date.today() + timedelta(days=365),
        )

        result = SpecialistServiceLayer.calculate_availability_percentage(
            self.specialist.id
        )

        self.assertGreater(result, 0.0)
        self.assertLessEqual(result, 100.0)


class SpecialistServiceLayerEdgeCasesTest(TestCase):
    """Test edge cases and boundary conditions"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="edgespec@test.com", password="testpass123"
        )

    def test_license_number_exactly_3_characters(self):
        """Test license number with exactly 3 characters (boundary)"""
        result = SpecialistServiceLayer.validate_license_number("ABC")
        self.assertEqual(result, "ABC")

    def test_license_number_exactly_30_characters(self):
        """Test license number with exactly 30 characters (boundary)"""
        license = "A" * 30
        result = SpecialistServiceLayer.validate_license_number(license)
        self.assertEqual(result, license)

    def test_years_experience_zero(self):
        """Test years experience at minimum (0)"""
        result = SpecialistServiceLayer.validate_years_experience(0)
        self.assertEqual(result, 0)

    def test_years_experience_sixty(self):
        """Test years experience at maximum (60)"""
        result = SpecialistServiceLayer.validate_years_experience(60)
        self.assertEqual(result, 60)

    def test_consultation_fee_minimum(self):
        """Test consultation fee at minimum"""
        result = SpecialistServiceLayer.validate_consultation_fee(Decimal("10.00"))
        self.assertEqual(result, Decimal("10.00"))

    def test_consultation_fee_maximum(self):
        """Test consultation fee at maximum"""
        result = SpecialistServiceLayer.validate_consultation_fee(Decimal("1000.00"))
        self.assertEqual(result, Decimal("1000.00"))

    def test_rating_minimum(self):
        """Test rating at minimum (0.00)"""
        result = SpecialistServiceLayer.validate_rating(Decimal("0.00"))
        self.assertEqual(result, Decimal("0.00"))

    def test_rating_maximum(self):
        """Test rating at maximum (5.00)"""
        result = SpecialistServiceLayer.validate_rating(Decimal("5.00"))
        self.assertEqual(result, Decimal("5.00"))

    def test_price_override_at_50_percent(self):
        """Test price override at exactly 50% (boundary)"""
        specialist = Specialist.objects.create(
            user=self.user,
            license_number="TEST123",
            specialization="therapist",
            years_experience=1,
            consultation_fee=Decimal("50.00"),
        )

        service = Service.objects.create(
            name="Test",
            category="therapy",
            duration_minutes=60,
            base_price=Decimal("100.00"),
        )

        price_override = service.base_price * Decimal("0.5")
        result = SpecialistServiceLayer.add_service_to_specialist(
            specialist.id, service.id, price_override=price_override
        )

        self.assertEqual(result.price_override, Decimal("50.00"))

    def test_price_override_at_3x(self):
        """Test price override at exactly 3x (boundary)"""
        specialist = Specialist.objects.create(
            user=self.user,
            license_number="TEST123",
            specialization="therapist",
            years_experience=1,
            consultation_fee=Decimal("50.00"),
        )

        service = Service.objects.create(
            name="Test",
            category="therapy",
            duration_minutes=60,
            base_price=Decimal("100.00"),
        )

        price_override = service.base_price * 3
        result = SpecialistServiceLayer.add_service_to_specialist(
            specialist.id, service.id, price_override=price_override
        )

        self.assertEqual(result.price_override, Decimal("300.00"))
