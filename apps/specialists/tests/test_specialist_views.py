from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from datetime import timedelta, time, date

from apps.specialists.models import Specialist, Service, SpecialistService, Availability
from apps.appointments.models import Appointment

User = get_user_model()


class SpecialistViewSetTest(TestCase):
    """Test cases for SpecialistViewSet"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create admin user
        self.admin_user = User.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            first_name="Admin",
            last_name="User",
            user_type="admin",
            is_staff=True,
            is_active=True,
        )

        # Create specialist user
        self.specialist_user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
            user_type="specialist",
            is_active=True,
        )

        # Create patient user
        self.patient_user = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            first_name="Jane",
            last_name="Patient",
            user_type="patient",
            is_active=True,
        )

        # Create specialist profile
        self.specialist = Specialist.objects.create(
            user=self.specialist_user,
            license_number="LIC123456",
            specialization="psychologist",
            qualifications="PhD in Psychology",
            years_experience=5,
            consultation_fee=Decimal("100.00"),
            is_accepting_new_patients=True,
            is_active=True,
            bio="Experienced psychologist",
        )

        # Create service
        self.service = Service.objects.create(
            name="Individual Therapy",
            category="therapy",
            duration_minutes=60,
            base_price=Decimal("120.00"),
            is_active=True,
        )

        # Add service to specialist
        self.specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
            is_available=True,
        )

        # Create availability
        self.availability = Availability.objects.create(
            specialist=self.specialist,
            day_of_week=0,  # Monday
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_recurring=True,
            valid_from=date.today(),
            valid_until=date.today() + timedelta(days=365),
        )

    # ============= List Tests =============

    def test_list_specialists_unauthenticated(self):
        """Test listing specialists without authentication"""
        response = self.client.get("/api/v2/specialists/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.json())

    def test_list_specialists_with_filters(self):
        """Test listing specialists with filters"""
        response = self.client.get(
            "/api/v2/specialists/", {"specialization": "psychologist"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("data", data)

    def test_list_specialists_with_min_rating(self):
        """Test listing specialists with minimum rating filter"""
        response = self.client.get("/api/v2/specialists/", {"min_rating": "4.0"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_specialists_with_search(self):
        """Test listing specialists with search query"""
        response = self.client.get("/api/v2/specialists/", {"search": "John"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("data", data)

    # ============= Retrieve Tests =============

    # Fix: 404 instead of 200 for unauthenticated access to specialist details
    def test_retrieve_specialist_unauthenticated(self):
        """Test retrieving specialist details without authentication"""
        response = self.client.get(f"/api/v2/specialists/{self.specialist.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("data", data)
        self.assertIn("stats", data["data"])

    def test_retrieve_specialist_not_found(self):
        """Test retrieving non-existent specialist"""
        response = self.client.get("/api/v2/specialists/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ============= Create Tests =============

    def test_create_specialist_as_admin(self):
        """Test creating specialist as admin"""
        self.client.force_authenticate(user=self.admin_user)

        # Create new user for specialist
        new_user = User.objects.create_user(
            email="newspec@test.com",
            password="testpass123",
            first_name="New",
            last_name="Specialist",
        )

        data = {
            "user_id": new_user.id,
            "license_number": "LIC789012",
            "specialization": "psychiatrist",
            "qualifications": "MD",
            "years_experience": 3,
            "consultation_fee": "150.00",
            "bio": "New specialist",
        }

        response = self.client.post("/api/v2/specialists-manage/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        self.assertIn("data", response_data)

    def test_create_specialist_as_patient(self):
        """Test creating specialist as patient (should fail)"""
        self.client.force_authenticate(user=self.patient_user)

        new_user = User.objects.create_user(
            email="newspec2@test.com",
            password="testpass123",
            first_name="New",
            last_name="Specialist",
        )

        data = {
            "user_id": new_user.id,
            "license_number": "LIC789013",
            "specialization": "psychiatrist",
            "years_experience": 3,
            "consultation_fee": "150.00",
        }

        response = self.client.post("/api/v2/specialists-manage/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_specialist_unauthenticated(self):
        """Test creating specialist without authentication"""
        new_user = User.objects.create_user(
            email="newspec3@test.com",
            password="testpass123",
            first_name="New",
            last_name="Specialist",
        )

        data = {
            "user_id": new_user.id,
            "license_number": "LIC789014",
            "specialization": "psychiatrist",
            "years_experience": 3,
            "consultation_fee": "150.00",
        }

        response = self.client.post("/api/v2/specialists-manage/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ============= Update Tests =============

    def test_update_specialist_as_owner(self):
        """Test updating specialist as the specialist themselves"""
        self.client.force_authenticate(user=self.specialist_user)

        data = {"bio": "Updated bio", "consultation_fee": "120.00"}

        response = self.client.patch(
            f"/api/v2/specialists-manage/{self.specialist.id}/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["data"]["bio"], "Updated bio")

    def test_update_specialist_as_admin(self):
        """Test updating specialist as admin"""
        self.client.force_authenticate(user=self.admin_user)

        data = {"years_experience": 10}

        response = self.client.patch(
            f"/api/v2/specialists-manage/{self.specialist.id}/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["data"]["years_experience"], 10)

    def test_update_specialist_as_different_specialist(self):
        """Test updating specialist as different specialist (should fail)"""
        # Create another specialist
        other_user = User.objects.create_user(
            email="other@test.com",
            password="testpass123",
            user_type="specialist",
        )
        other_specialist = Specialist.objects.create(
            user=other_user,
            license_number="OTHER123",
            specialization="therapist",
            years_experience=2,
            consultation_fee=Decimal("80.00"),
        )

        self.client.force_authenticate(user=other_user)

        data = {"bio": "Hacked bio"}

        response = self.client.patch(
            f"/api/v2/specialists-manage/{self.specialist.id}/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ============= Delete Tests =============

    def test_delete_specialist_as_admin(self):
        """Test deleting specialist as admin"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.delete(
            f"/api/v2/specialists-manage/{self.specialist.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify specialist is deactivated, not deleted
        self.specialist.refresh_from_db()
        self.assertFalse(self.specialist.is_active)

    def test_delete_specialist_as_patient(self):
        """Test deleting specialist as patient (should fail)"""
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.delete(
            f"/api/v2/specialists-manage/{self.specialist.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ============= Specialist Services Tests =============

    def test_get_specialist_services(self):
        """Test getting specialist services"""
        response = self.client.get(
            f"/api/v2/specialists/{self.specialist.id}/services/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)

    # ============= Add Service Tests =============

    def test_add_service_as_specialist_owner(self):
        """Test adding service as the specialist themselves"""
        self.client.force_authenticate(user=self.specialist_user)

        # Create new service
        new_service = Service.objects.create(
            name="Group Therapy",
            category="therapy",
            duration_minutes=90,
            base_price=Decimal("150.00"),
        )

        data = {"service_id": new_service.id, "price_override": "140.00"}

        response = self.client.post(
            f"/api/v2/specialists-manage/{self.specialist.id}/add-service/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_add_service_as_admin(self):
        """Test adding service as admin"""
        self.client.force_authenticate(user=self.admin_user)

        new_service = Service.objects.create(
            name="Family Therapy",
            category="therapy",
            duration_minutes=90,
            base_price=Decimal("180.00"),
        )

        data = {"service_id": new_service.id}

        response = self.client.post(
            f"/api/v2/specialists-manage/{self.specialist.id}/add-service/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_add_service_as_different_specialist(self):
        """Test adding service as different specialist (should fail)"""
        other_user = User.objects.create_user(
            email="other2@test.com",
            password="testpass123",
            user_type="specialist",
        )
        Specialist.objects.create(
            user=other_user,
            license_number="OTHER456",
            specialization="therapist",
            years_experience=2,
            consultation_fee=Decimal("80.00"),
        )

        self.client.force_authenticate(user=other_user)

        new_service = Service.objects.create(
            name="Art Therapy",
            category="therapy",
            duration_minutes=60,
            base_price=Decimal("100.00"),
        )

        data = {"service_id": new_service.id}

        response = self.client.post(
            f"/api/v2/specialists-manage/{self.specialist.id}/add-service/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ============= Remove Service Tests =============

    def test_remove_service_as_specialist_owner(self):
        """Test removing service as the specialist themselves"""
        self.client.force_authenticate(user=self.specialist_user)

        response = self.client.delete(
            f"/api/v2/specialists-manage/{self.specialist.id}/remove-service/{self.service.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_remove_service_as_admin(self):
        """Test removing service as admin"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.delete(
            f"/api/v2/specialists-manage/{self.specialist.id}/remove-service/{self.service.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ============= Specialist Availability Tests =============

    # Endpoint Does not Exists
    def test_get_specialist_availability(self):
        """Test getting specialist availability"""
        response = self.client.get(
            f"/api/v2/specialists/{self.specialist.id}/availability/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)

    # ============= Available Slots Tests =============

    def test_get_available_slots(self):
        """Test getting available slots for a specific date"""
        # Get next Monday
        today = date.today()
        days_ahead = 0 - today.weekday()  # Monday is 0
        if days_ahead <= 0:
            days_ahead += 7
        next_monday = today + timedelta(days=days_ahead)

        response = self.client.get(
            f"/api/v2/specialists/{self.specialist.id}/available-slots/{next_monday.strftime('%Y-%m-%d')}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("data", data)
        self.assertIn("available_slots", data["data"])

    # ============= By Specialization Tests =============

    def test_get_specialists_by_specialization(self):
        """Test getting specialists grouped by specialization"""
        response = self.client.get("/api/v2/specialists/summary/by-specialization/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], dict)

    # ============= Activate Specialist Tests =============

    def test_activate_specialist_as_admin(self):
        """Test activating specialist as admin"""
        # Deactivate first
        self.specialist.is_active = False
        self.specialist.save()

        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            f"/api/v2/specialists-manage/{self.specialist.id}/activate/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.specialist.refresh_from_db()
        self.assertTrue(self.specialist.is_active)

    def test_activate_specialist_as_patient(self):
        """Test activating specialist as patient (should fail)"""
        self.specialist.is_active = False
        self.specialist.save()

        self.client.force_authenticate(user=self.patient_user)

        response = self.client.post(
            f"/api/v2/specialists-manage/{self.specialist.id}/activate/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ============= Deactivate Specialist Tests =============

    def test_deactivate_specialist_as_admin(self):
        """Test deactivating specialist as admin"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            f"/api/v2/specialists-manage/{self.specialist.id}/deactivate/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.specialist.refresh_from_db()
        self.assertFalse(self.specialist.is_active)

    def test_deactivate_specialist_as_patient(self):
        """Test deactivating specialist as patient (should fail)"""
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.post(
            f"/api/v2/specialists-manage/{self.specialist.id}/deactivate/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SpecialistViewSetPaginationTest(TestCase):
    """Test pagination for specialist list"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create multiple specialists
        for i in range(25):
            user = User.objects.create_user(
                email=f"spec{i}@test.com",
                password="testpass123",
                first_name=f"Specialist",
                last_name=f"{i}",
            )
            Specialist.objects.create(
                user=user,
                license_number=f"LIC{i:06d}",
                specialization="psychologist",
                years_experience=i + 1,
                consultation_fee=Decimal("100.00"),
            )

    def test_list_specialists_with_pagination(self):
        """Test specialist list with pagination"""
        response = self.client.get("/api/v2/specialists/", {"page": 1, "page_size": 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("pagination", data)
        self.assertEqual(data["pagination"]["page"], 1)
        self.assertEqual(data["pagination"]["page_size"], 10)

    def test_list_specialists_page_2(self):
        """Test getting second page of specialists"""
        response = self.client.get("/api/v2/specialists/", {"page": 2, "page_size": 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["pagination"]["page"], 2)


class SpecialistViewSetErrorHandlingTest(TestCase):
    """Test error handling in specialist views"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            user_type="admin",
            is_staff=True,
        )

    def test_create_specialist_with_invalid_data(self):
        """Test creating specialist with invalid data"""
        self.client.force_authenticate(user=self.admin_user)

        user = User.objects.create_user(
            email="newspec@test.com", password="testpass123"
        )

        data = {
            "user_id": user.id,
            "license_number": "AB",  # Too short
            "specialization": "psychologist",
            "years_experience": 5,
            "consultation_fee": "100.00",
        }

        response = self.client.post("/api/v2/specialists-manage/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_specialist_with_duplicate_license(self):
        """Test creating specialist with duplicate license number"""
        self.client.force_authenticate(user=self.admin_user)

        # Create first specialist
        user1 = User.objects.create_user(email="spec1@test.com", password="testpass123")
        Specialist.objects.create(
            user=user1,
            license_number="LIC123456",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("100.00"),
        )

        # Try to create second with same license
        user2 = User.objects.create_user(email="spec2@test.com", password="testpass123")

        data = {
            "user_id": user2.id,
            "license_number": "LIC123456",  # Duplicate
            "specialization": "psychiatrist",
            "years_experience": 3,
            "consultation_fee": "120.00",
        }

        response = self.client.post("/api/v2/specialists-manage/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_specialist_with_invalid_years_experience(self):
        """Test updating specialist with invalid years experience"""
        user = User.objects.create_user(
            email="spec@test.com", password="testpass123", user_type="specialist"
        )
        specialist = Specialist.objects.create(
            user=user,
            license_number="LIC123456",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("100.00"),
        )

        self.client.force_authenticate(user=self.admin_user)

        data = {"years_experience": -1}  # Invalid

        response = self.client.patch(
            f"/api/v2/specialists-manage/{specialist.id}/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_nonexistent_service_to_specialist(self):
        """Test adding non-existent service to specialist"""
        user = User.objects.create_user(
            email="spec@test.com", password="testpass123", user_type="specialist"
        )
        specialist = Specialist.objects.create(
            user=user,
            license_number="LIC123456",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("100.00"),
        )

        self.client.force_authenticate(user=user)

        data = {"service_id": 99999}  # Non-existent

        response = self.client.post(
            f"/api/v2/specialists-manage/{specialist.id}/add-service/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
