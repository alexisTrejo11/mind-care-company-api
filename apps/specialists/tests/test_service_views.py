from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal

from apps.specialists.models import Specialist, Service, SpecialistService

User = get_user_model()


class ServiceViewSetTest(TestCase):
    """Test cases for ServiceViewSet"""

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
        )

        # Create staff user
        self.staff_user = User.objects.create_user(
            email="staff@test.com",
            password="testpass123",
            first_name="Staff",
            last_name="User",
            user_type="staff",
            is_staff=True,
        )

        # Create patient user
        self.patient_user = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            first_name="Jane",
            last_name="Patient",
            user_type="patient",
        )

        # Create specialist user
        self.specialist_user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            first_name="John",
            last_name="Specialist",
            user_type="specialist",
        )

        # Create specialist profile
        self.specialist = Specialist.objects.create(
            user=self.specialist_user,
            license_number="LIC123456",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=Decimal("100.00"),
        )

        # Create services
        self.service1 = Service.objects.create(
            name="Individual Therapy",
            description="One-on-one therapy session",
            category="therapy",
            duration_minutes=60,
            base_price=Decimal("120.00"),
            is_active=True,
        )

        self.service2 = Service.objects.create(
            name="Group Therapy",
            description="Group therapy session",
            category="therapy",
            duration_minutes=90,
            base_price=Decimal("80.00"),
            is_active=True,
        )

        # Add service to specialist
        self.specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service1,
            is_available=True,
            price_override=Decimal("110.00"),
        )

    # ============= List Tests =============

    def test_list_services_unauthenticated(self):
        """Test listing services without authentication"""
        response = self.client.get("/api/v2/services/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("data", data)

    def test_list_services_with_category_filter(self):
        """Test listing services with category filter"""
        response = self.client.get("/api/v2/services/", {"category": "therapy"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("data", data)

    def test_list_services_active_only(self):
        """Test listing only active services"""
        # Create inactive service
        Service.objects.create(
            name="Inactive Service",
            category="therapy",
            duration_minutes=60,
            base_price=Decimal("100.00"),
            is_active=False,
        )

        response = self.client.get("/api/v2/services/", {"active_only": "true"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # All returned services should be active
        for service in data["data"]:
            self.assertTrue(service.get("is_active", True))

    def test_list_services_with_price_range(self):
        """Test listing services with price range filter"""
        response = self.client.get(
            "/api/v2/services/", {"min_price": "50.00", "max_price": "150.00"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_services_with_duration_filter(self):
        """Test listing services with duration filter"""
        response = self.client.get(
            "/api/v2/services/", {"min_duration": 30, "max_duration": 90}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ============= Retrieve Tests =============

    def test_retrieve_service_unauthenticated(self):
        """Test retrieving service details without authentication"""
        response = self.client.get(f"/api/v2/services/{self.service1.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("data", data)
        self.assertIn("offered_by", data["data"])

    def test_retrieve_service_with_specialists(self):
        """Test retrieving service shows specialists offering it"""
        response = self.client.get(f"/api/v2/services/{self.service1.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("offered_by", data["data"])
        self.assertGreater(data["data"]["offered_by"]["total_specialists"], 0)

    def test_retrieve_service_not_found(self):
        """Test retrieving non-existent service"""
        response = self.client.get("/api/v2/services/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ============= Create Tests =============

    def test_create_service_as_admin(self):
        """Test creating service as admin"""
        self.client.force_authenticate(user=self.admin_user)

        data = {
            "name": "Family Therapy",
            "description": "Family counseling session",
            "category": "therapy",
            "duration_minutes": 90,
            "base_price": "150.00",
        }

        response = self.client.post("/api/v2/services/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        self.assertIn("data", response_data)
        self.assertEqual(response_data["data"]["name"], "Family Therapy")

    def test_create_service_as_staff(self):
        """Test creating service as staff"""
        self.client.force_authenticate(user=self.staff_user)

        data = {
            "name": "Couples Therapy",
            "category": "therapy",
            "duration_minutes": 60,
            "base_price": "130.00",
        }

        response = self.client.post("/api/v2/services/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_service_as_patient(self):
        """Test creating service as patient (should fail)"""
        self.client.force_authenticate(user=self.patient_user)

        data = {
            "name": "Test Service",
            "category": "therapy",
            "duration_minutes": 60,
            "base_price": "100.00",
        }

        response = self.client.post("/api/v2/services/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_service_unauthenticated(self):
        """Test creating service without authentication"""
        data = {
            "name": "Test Service",
            "category": "therapy",
            "duration_minutes": 60,
            "base_price": "100.00",
        }

        response = self.client.post("/api/v2/services/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_service_with_duplicate_name_in_category(self):
        """Test creating service with duplicate name in same category"""
        self.client.force_authenticate(user=self.admin_user)

        data = {
            "name": "Individual Therapy",  # Already exists in therapy category
            "category": "therapy",
            "duration_minutes": 60,
            "base_price": "120.00",
        }

        response = self.client.post("/api/v2/services/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_create_service_with_invalid_duration(self):
        """Test creating service with invalid duration"""
        self.client.force_authenticate(user=self.admin_user)

        data = {
            "name": "Test Service",
            "category": "therapy",
            "duration_minutes": 25,  # Not 15-minute increment
            "base_price": "100.00",
        }

        response = self.client.post("/api/v2/services/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_service_with_invalid_price(self):
        """Test creating service with invalid price"""
        self.client.force_authenticate(user=self.admin_user)

        data = {
            "name": "Test Service",
            "category": "therapy",
            "duration_minutes": 60,
            "base_price": "2.00",  # Too low
        }

        response = self.client.post("/api/v2/services/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ============= Update Tests =============

    def test_update_service_as_admin(self):
        """Test updating service as admin"""
        self.client.force_authenticate(user=self.admin_user)

        data = {"base_price": "130.00", "description": "Updated description"}

        response = self.client.patch(
            f"/api/v2/services/{self.service1.id}/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["data"]["base_price"], "130.00")

    def test_update_service_as_staff(self):
        """Test updating service as staff"""
        self.client.force_authenticate(user=self.staff_user)

        data = {"duration_minutes": 75}

        response = self.client.patch(
            f"/api/v2/services/{self.service1.id}/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_service_as_patient(self):
        """Test updating service as patient (should fail)"""
        self.client.force_authenticate(user=self.patient_user)

        data = {"base_price": "200.00"}

        response = self.client.patch(
            f"/api/v2/services/{self.service1.id}/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_service_with_invalid_duration(self):
        """Test updating service with invalid duration"""
        self.client.force_authenticate(user=self.admin_user)

        data = {"duration_minutes": 35}  # Not 15-minute increment

        response = self.client.patch(
            f"/api/v2/services/{self.service1.id}/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ============= Delete (Deactivate) Tests =============

    def test_delete_service_as_admin(self):
        """Test deleting service as admin (actually deactivates)"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.delete(f"/api/v2/services/{self.service1.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify service is deactivated, not deleted
        self.service1.refresh_from_db()
        self.assertFalse(self.service1.is_active)

    def test_delete_service_as_patient(self):
        """Test deleting service as patient (should fail)"""
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.delete(f"/api/v2/services/{self.service1.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ============= Reactivate Tests =============

    def test_reactivate_service_as_admin(self):
        """Test reactivating service as admin"""
        # Deactivate first
        self.service1.is_active = False
        self.service1.save()

        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(f"/api/v2/services/{self.service1.id}/reactivate/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.service1.refresh_from_db()
        self.assertTrue(self.service1.is_active)

    def test_reactivate_service_as_patient(self):
        """Test reactivating service as patient (should fail)"""
        self.service1.is_active = False
        self.service1.save()

        self.client.force_authenticate(user=self.patient_user)

        response = self.client.post(f"/api/v2/services/{self.service1.id}/reactivate/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ============= Service Specialists Tests =============

    def test_get_service_specialists(self):
        """Test getting specialists offering a service"""
        response = self.client.get(f"/api/v2/services/{self.service1.id}/specialists/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("data", data)
        self.assertIn("specialists", data["data"])
        self.assertGreater(data["data"]["total_specialists"], 0)

    def test_get_specialists_for_service_with_no_specialists(self):
        """Test getting specialists for service with no specialists offering it"""
        # Create service with no specialists
        new_service = Service.objects.create(
            name="New Service",
            category="wellness",
            duration_minutes=45,
            base_price=Decimal("90.00"),
        )

        response = self.client.get(f"/api/v2/services/{new_service.id}/specialists/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["data"]["total_specialists"], 0)

    # ============= By Category Tests =============

    def test_get_services_by_category(self):
        """Test getting services grouped by category"""
        response = self.client.get("/api/v2/services/by-category/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], dict)

    # ============= Stats Tests =============

    def test_get_service_stats_as_admin(self):
        """Test getting service statistics as admin"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(
            "/api/v2/services/stats/", {"period": "month", "include_inactive": False}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("data", data)
        self.assertIn("summary", data["data"])
        self.assertIn("category_distribution", data["data"])

    def test_get_service_stats_as_patient(self):
        """Test getting service statistics as patient (should fail)"""
        self.client.force_authenticate(user=self.patient_user)

        response = self.client.get(
            "/api/v2/services/stats/", {"period": "month", "include_inactive": False}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_service_stats_with_invalid_period(self):
        """Test getting service statistics with invalid period"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(
            "/api/v2/services/stats/",
            {"period": "invalid", "include_inactive": False},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ============= Add To Specialist Tests =============

    def test_add_service_to_specialist_as_admin(self):
        """Test adding service to specialist as admin"""
        self.client.force_authenticate(user=self.admin_user)

        data = {"specialist_id": self.specialist.id, "price_override": "100.00"}

        response = self.client.post(
            f"/api/v2/services/{self.service2.id}/add-to-specialist/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_add_service_to_specialist_as_specialist_owner(self):
        """Test adding service to own profile as specialist"""
        self.client.force_authenticate(user=self.specialist_user)

        data = {"specialist_id": self.specialist.id}

        response = self.client.post(
            f"/api/v2/services/{self.service2.id}/add-to-specialist/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_add_service_to_different_specialist(self):
        """Test adding service to different specialist (should fail)"""
        # Create another specialist
        other_user = User.objects.create_user(
            email="other@test.com", password="testpass123", user_type="specialist"
        )
        other_specialist = Specialist.objects.create(
            user=other_user,
            license_number="OTHER123",
            specialization="therapist",
            years_experience=2,
            consultation_fee=Decimal("80.00"),
        )

        self.client.force_authenticate(user=self.specialist_user)

        data = {"specialist_id": other_specialist.id}

        response = self.client.post(
            f"/api/v2/services/{self.service2.id}/add-to-specialist/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_add_service_without_specialist_id(self):
        """Test adding service without specialist_id"""
        self.client.force_authenticate(user=self.admin_user)

        data = {}  # Missing specialist_id

        response = self.client.post(
            f"/api/v2/services/{self.service2.id}/add-to-specialist/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_service_to_nonexistent_specialist(self):
        """Test adding service to non-existent specialist"""
        self.client.force_authenticate(user=self.admin_user)

        data = {"specialist_id": 99999}

        response = self.client.post(
            f"/api/v2/services/{self.service2.id}/add-to-specialist/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ServiceViewSetPaginationTest(TestCase):
    """Test pagination for service list"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create multiple services
        for i in range(25):
            Service.objects.create(
                name=f"Service {i}",
                category="therapy",
                duration_minutes=60,
                base_price=Decimal("100.00") + Decimal(i),
            )

    def test_list_services_default_pagination(self):
        """Test service list with default pagination"""
        response = self.client.get("/api/v2/services/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ServiceViewSetSearchTest(TestCase):
    """Test search functionality for services"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        Service.objects.create(
            name="Individual Therapy",
            description="Personal counseling",
            category="therapy",
            duration_minutes=60,
            base_price=Decimal("120.00"),
        )

        Service.objects.create(
            name="Group Therapy",
            description="Group sessions",
            category="therapy",
            duration_minutes=90,
            base_price=Decimal("80.00"),
        )

        Service.objects.create(
            name="Mental Health Assessment",
            description="Comprehensive evaluation",
            category="mental_health",
            duration_minutes=45,
            base_price=Decimal("150.00"),
        )

    def test_search_services_by_name(self):
        """Test searching services by name"""
        response = self.client.get("/api/v2/services/", {"search": "Individual"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertGreater(len(data["data"]), 0)

    def test_search_services_by_description(self):
        """Test searching services by description"""
        response = self.client.get("/api/v2/services/", {"search": "counseling"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_services_no_results(self):
        """Test searching services with no results"""
        response = self.client.get("/api/v2/services/", {"search": "nonexistent"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # May return empty or still have pagination structure
        self.assertIn("data", data)


class ServiceViewSetOrderingTest(TestCase):
    """Test ordering functionality for services"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        Service.objects.create(
            name="Expensive Service",
            category="therapy",
            duration_minutes=60,
            base_price=Decimal("200.00"),
        )

        Service.objects.create(
            name="Cheap Service",
            category="therapy",
            duration_minutes=30,
            base_price=Decimal("50.00"),
        )

        Service.objects.create(
            name="Medium Service",
            category="wellness",
            duration_minutes=45,
            base_price=Decimal("100.00"),
        )

    def test_order_services_by_price_asc(self):
        """Test ordering services by price ascending"""
        response = self.client.get("/api/v2/services/", {"ordering": "base_price"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_order_services_by_price_desc(self):
        """Test ordering services by price descending"""
        response = self.client.get("/api/v2/services/", {"ordering": "-base_price"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_order_services_by_duration(self):
        """Test ordering services by duration"""
        response = self.client.get(
            "/api/v2/services/", {"ordering": "duration_minutes"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_order_services_by_name(self):
        """Test ordering services by name"""
        response = self.client.get("/api/v2/services/", {"ordering": "name"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
