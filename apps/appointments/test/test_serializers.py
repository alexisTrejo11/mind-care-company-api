from django.test import TestCase, RequestFactory
from django.utils import timezone
from datetime import timedelta
from apps.appointments.serializers import (
    AppointmentCreateSerializer,
    AppointmentSerializer,
)
from apps.appointments.models import Appointment
from apps.specialists.models import Specialist
from apps.users.models import User
from apps.core.exceptions.base_exceptions import ValidationError, NotFoundError


class AppointmentCreateSerializerTestCase(TestCase):
    """Example test suite for AppointmentCreateSerializer"""

    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()

        # Create patient user
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
            user_type="patient",
        )

        # Create specialist user
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
        )

    def test_create_serializer_valid_data(self):
        """Test serializer with valid appointment data"""
        # Prepare valid data
        start_time = timezone.now() + timedelta(days=7, hours=2)
        end_time = start_time + timedelta(minutes=30)

        data = {
            "specialist_id": self.specialist.id,
            "patient_id": self.patient.id,
            "appointment_type": "consultation",
            "appointment_date": start_time,
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": 30,
            "notes": "First consultation",
        }

        # Create mock request with user context
        request = self.factory.post("/appointments/")
        request.user = self.patient

        # Initialize serializer with data and context
        serializer = AppointmentCreateSerializer(
            data=data, context={"request": request}
        )

        # Validate serializer
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["patient"], self.patient)
        self.assertEqual(serializer.validated_data["specialist"], self.specialist)

    def test_create_serializer_invalid_start_end_time(self):
        """Test serializer rejects when start_time is after end_time"""
        start_time = timezone.now() + timedelta(days=7, hours=2)
        end_time = start_time - timedelta(minutes=30)  # Invalid: end before start

        data = {
            "specialist_id": self.specialist.id,
            "patient_id": self.patient.id,
            "appointment_type": "consultation",
            "appointment_date": start_time,
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": 30,
        }

        request = self.factory.post("/appointments/")
        request.user = self.patient

        serializer = AppointmentCreateSerializer(
            data=data, context={"request": request}
        )

        # Should not be valid
        self.assertFalse(serializer.is_valid())
        self.assertIn("Start time must be before end time", str(serializer.errors))

    def test_create_serializer_specialist_not_found(self):
        """Test serializer rejects non-existent specialist"""
        start_time = timezone.now() + timedelta(days=7, hours=2)
        end_time = start_time + timedelta(minutes=30)

        data = {
            "specialist_id": 99999,  # Non-existent specialist
            "patient_id": self.patient.id,
            "appointment_type": "consultation",
            "appointment_date": start_time,
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": 30,
        }

        request = self.factory.post("/appointments/")
        request.user = self.patient

        serializer = AppointmentCreateSerializer(
            data=data, context={"request": request}
        )

        # Should raise NotFoundError during validation
        with self.assertRaises(NotFoundError):
            serializer.is_valid(raise_exception=True)

    def test_create_serializer_patient_auto_assigned(self):
        """Test patient is auto-assigned from request user"""
        start_time = timezone.now() + timedelta(days=7, hours=2)
        end_time = start_time + timedelta(minutes=30)

        data = {
            "specialist_id": self.specialist.id,
            # No patient_id provided
            "appointment_type": "consultation",
            "appointment_date": start_time,
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": 30,
        }

        request = self.factory.post("/appointments/")
        request.user = self.patient

        serializer = AppointmentCreateSerializer(
            data=data, context={"request": request}
        )

        self.assertTrue(serializer.is_valid())
        # Patient should be auto-assigned from request user
        self.assertEqual(serializer.validated_data["patient"], self.patient)


class AppointmentSerializerTestCase(TestCase):
    """Example test for read-only serializer"""

    def setUp(self):
        """Set up test data"""
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
            user_type="patient",
        )

        specialist_user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            first_name="Dr. Jane",
            last_name="Smith",
            user_type="specialist",
        )

        self.specialist = Specialist.objects.create(
            user=specialist_user,
            license_number="LIC123456",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=100.00,
        )

    def test_serializer_contains_expected_fields(self):
        """Test serializer returns expected fields"""
        start_time = timezone.now() + timedelta(days=7, hours=2)
        end_time = start_time + timedelta(minutes=30)

        appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=start_time,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=30,
            status="scheduled",
        )

        serializer = AppointmentSerializer(appointment)
        data = serializer.data

        # Check expected fields are present
        self.assertIn("id", data)
        self.assertIn("patient_name", data)
        self.assertIn("specialist_name", data)
        self.assertIn("appointment_type", data)
        self.assertIn("status", data)

        # Check computed fields
        self.assertEqual(data["patient_name"], "John Doe")
        self.assertEqual(data["specialist_name"], "Dr. Jane Smith")
        self.assertEqual(data["appointment_type"], "consultation")
