from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status

from apps.appointments.models import Appointment
from apps.specialists.models import Specialist
from apps.users.models import User


class AppointmentViewSetTestCase(TestCase):
    """Test suite for AppointmentViewSet"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create users
        self.patient = User.objects.create_user(
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

        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            first_name="Admin",
            last_name="User",
            user_type="admin",
            is_staff=True,
        )

        # Create specialist
        self.specialist = Specialist.objects.create(
            user=self.specialist_user,
            license_number="LIC123456",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=100.00,
            is_active=True,
            max_daily_appointments=20,
        )

        # Define appointment times
        self.start_time = timezone.now() + timedelta(days=7, hours=2)
        self.start_time = self.start_time.replace(
            hour=10, minute=0, second=0, microsecond=0
        )
        self.end_time = self.start_time + timedelta(minutes=30)

        # Create test appointment
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=30,
            status="scheduled",
        )

        # URLs
        self.list_url = reverse("appointment-list")
        self.detail_url = reverse(
            "appointment-detail", kwargs={"pk": self.appointment.pk}
        )
        self.cancel_url = reverse(
            "appointment-cancel", kwargs={"pk": self.appointment.pk}
        )
        self.reschedule_url = reverse(
            "appointment-reschedule", kwargs={"pk": self.appointment.pk}
        )
        self.stats_url = reverse("appointment-stats")
        self.today_url = reverse("appointment-today-appointments")

    def get_valid_appointment_time(self, days_ahead=10):
        """Helper to get a valid appointment time (weekday, within clinic hours)"""
        # Start from days_ahead days in the future at 10 AM
        future_date = timezone.now() + timedelta(days=days_ahead)
        future_date = future_date.replace(hour=10, minute=0, second=0, microsecond=0)

        # If it's a weekend, move to next Monday
        while future_date.weekday() >= 5:  # Saturday or Sunday
            future_date += timedelta(days=1)

        return future_date

    # =============================================
    # Tests for List Appointments
    # =============================================

    def test_list_appointments_unauthenticated(self):
        """Test listing appointments without authentication"""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_appointments_as_patient(self):
        """Test patient can list only their own appointments"""
        self.client.force_authenticate(user=self.patient)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Patient should see only their appointment
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["patient"], self.patient.id)

    def test_list_appointments_as_specialist(self):
        """Test specialist can list their appointments"""
        self.client.force_authenticate(user=self.specialist_user)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Specialist should see appointments assigned to them
        self.assertEqual(len(response.data["data"]), 1)

    def test_list_appointments_with_filters(self):
        """Test filtering appointments by status"""
        self.client.force_authenticate(user=self.patient)
        response = self.client.get(self.list_url, {"status": "scheduled"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 1)

    def test_list_appointments_search(self):
        """Test searching appointments"""
        self.client.force_authenticate(user=self.patient)
        response = self.client.get(self.list_url, {"search": "John"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["data"]), 1)

    # =============================================
    # Tests for Retrieve Appointment
    # =============================================

    def test_retrieve_appointment_success(self):
        """Test retrieving appointment details"""
        self.client.force_authenticate(user=self.patient)
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["id"], self.appointment.id)
        self.assertEqual(response.data["data"]["status"], "scheduled")

    def test_retrieve_appointment_not_found(self):
        """Test retrieving non-existent appointment"""
        self.client.force_authenticate(user=self.patient)
        url = reverse("appointment-detail", kwargs={"pk": 99999})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_appointment_other_patient(self):
        """Test patient cannot retrieve another patient's appointment"""
        other_patient = User.objects.create_user(
            email="other@test.com",
            password="testpass123",
            first_name="Other",
            last_name="Patient",
            user_type="patient",
        )

        self.client.force_authenticate(user=other_patient)
        response = self.client.get(self.detail_url)

        # Should not find it (filtered by queryset)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # =============================================
    # Tests for Create Appointment
    # =============================================

    def test_create_appointment_success(self):
        """Test creating appointment with valid data"""
        self.client.force_authenticate(user=self.patient)

        start = timezone.now() + timedelta(days=10, hours=2)
        start = start.replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=30)

        data = {
            "specialist_id": self.specialist.id,
            "appointment_type": "therapy",
            "appointment_date": start.isoformat(),
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "duration_minutes": 30,
            "notes": "Initial consultation",
        }

        response = self.client.post(self.list_url, data, format="json")

        if response.status_code != status.HTTP_201_CREATED:
            print(f"Create failed: {response.data}")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("Appointment scheduled successfully", response.data["message"])
        self.assertEqual(Appointment.objects.count(), 2)

    def test_create_appointment_invalid_time(self):
        """Test creating appointment with start time after end time"""
        self.client.force_authenticate(user=self.patient)

        start = timezone.now() + timedelta(days=10, hours=2)
        end = start - timedelta(minutes=30)  # Invalid: end before start

        data = {
            "specialist_id": self.specialist.id,
            "appointment_type": "consultation",
            "appointment_date": start.isoformat(),
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "duration_minutes": 30,
        }

        response = self.client.post(self.list_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_appointment_nonexistent_specialist(self):
        """Test creating appointment with non-existent specialist"""
        self.client.force_authenticate(user=self.patient)

        start = timezone.now() + timedelta(days=10, hours=2)
        end = start + timedelta(minutes=30)

        data = {
            "specialist_id": 99999,  # Non-existent
            "appointment_type": "consultation",
            "appointment_date": start.isoformat(),
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "duration_minutes": 30,
        }

        response = self.client.post(self.list_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_appointment_missing_fields(self):
        """Test creating appointment with missing required fields"""
        self.client.force_authenticate(user=self.patient)

        data = {
            "specialist_id": self.specialist.id,
            # Missing other required fields
        }

        response = self.client.post(self.list_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_appointment_unauthenticated(self):
        """Test creating appointment without authentication"""
        start = timezone.now() + timedelta(days=10, hours=2)
        end = start + timedelta(minutes=30)

        data = {
            "specialist_id": self.specialist.id,
            "appointment_type": "consultation",
            "appointment_date": start.isoformat(),
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "duration_minutes": 30,
        }

        response = self.client.post(self.list_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # =============================================
    # Tests for Cancel Appointment
    # =============================================

    def test_cancel_appointment_success(self):
        """Test cancelling appointment successfully"""
        # Create appointment far enough in the future (> 24 hours)
        future_start = timezone.now() + timedelta(days=7)
        future_end = future_start + timedelta(minutes=30)

        appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=future_start,
            start_time=future_start,
            end_time=future_end,
            duration_minutes=30,
            status="scheduled",
        )

        self.client.force_authenticate(user=self.admin)
        url = reverse("appointment-cancel", kwargs={"pk": appointment.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "cancelled")

    def test_cancel_appointment_already_cancelled(self):
        """Test cancelling already cancelled appointment"""
        self.appointment.status = "cancelled"
        self.appointment.save()

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.cancel_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_appointment_other_patient(self):
        """Test patient cannot cancel another patient's appointment"""
        other_patient = User.objects.create_user(
            email="other2@test.com",
            password="testpass123",
            first_name="Other",
            last_name="Patient2",
            user_type="patient",
        )

        self.client.force_authenticate(user=other_patient)
        response = self.client.post(self.cancel_url)

        # Patient gets 403 because cancel requires staff/specialist permissions
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cancel_appointment_unauthenticated(self):
        """Test cancelling appointment without authentication"""
        response = self.client.post(self.cancel_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # =============================================
    # Tests for Reschedule Appointment
    # =============================================

    def test_reschedule_appointment_success(self):
        """Test rescheduling appointment successfully"""
        self.client.force_authenticate(user=self.admin)

        new_start = self.start_time + timedelta(days=3)  # At least 2 hours different
        new_start = new_start.replace(hour=10, minute=0, second=0, microsecond=0)
        new_end = new_start + timedelta(minutes=45)

        data = {
            "new_appointment_date": new_start.isoformat(),
            "new_start_time": new_start.isoformat(),
            "new_end_time": new_end.isoformat(),
            "new_duration_minutes": 45,
            "reason": "Patient request",
        }

        response = self.client.post(self.reschedule_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("rescheduled successfully", response.data["message"])

    def test_reschedule_appointment_invalid_time_difference(self):
        """Test rescheduling with less than 2 hours difference"""
        self.client.force_authenticate(user=self.admin)

        new_start = self.start_time + timedelta(minutes=30)  # Less than 2 hours
        new_end = new_start + timedelta(minutes=30)

        data = {
            "new_appointment_date": new_start.isoformat(),
            "new_start_time": new_start.isoformat(),
            "new_end_time": new_end.isoformat(),
            "new_duration_minutes": 30,
        }

        response = self.client.post(self.reschedule_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reschedule_appointment_completed_status(self):
        """Test rescheduling completed appointment fails"""
        self.appointment.status = "completed"
        self.appointment.save()

        self.client.force_authenticate(user=self.admin)

        new_start = self.start_time + timedelta(days=3)
        new_end = new_start + timedelta(minutes=30)

        data = {
            "new_appointment_date": new_start.isoformat(),
            "new_start_time": new_start.isoformat(),
            "new_end_time": new_end.isoformat(),
            "new_duration_minutes": 30,
        }

        response = self.client.post(self.reschedule_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reschedule_appointment_unauthenticated(self):
        """Test rescheduling without authentication"""
        new_start = self.start_time + timedelta(days=3)
        new_end = new_start + timedelta(minutes=30)

        data = {
            "new_appointment_date": new_start.isoformat(),
            "new_start_time": new_start.isoformat(),
            "new_end_time": new_end.isoformat(),
            "new_duration_minutes": 30,
        }

        response = self.client.post(self.reschedule_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # =============================================
    # Tests for Statistics
    # =============================================

    def test_stats_as_specialist(self):
        """Test getting statistics as specialist"""
        self.client.force_authenticate(user=self.specialist_user)

        response = self.client.get(self.stats_url, {"period": "month"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)
        self.assertIn("total_appointments", response.data["data"])

    def test_stats_as_admin(self):
        """Test getting statistics as admin"""
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.stats_url, {"period": "week"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)

    def test_stats_as_patient_forbidden(self):
        """Test patient cannot access statistics"""
        self.client.force_authenticate(user=self.patient)

        response = self.client.get(self.stats_url, {"period": "month"})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_stats_invalid_period(self):
        """Test statistics with invalid period"""
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.stats_url, {"period": "invalid"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_stats_unauthenticated(self):
        """Test statistics without authentication"""
        response = self.client.get(self.stats_url, {"period": "month"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # =============================================
    # Tests for Today's Appointments
    # =============================================

    def test_today_appointments_as_specialist(self):
        """Test getting today's appointments as specialist"""
        # Create appointment for today
        today_start = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(minutes=30)

        Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=today_start,  # Use timezone-aware datetime
            start_time=today_start,
            end_time=today_end,
            duration_minutes=30,
            status="scheduled",
        )

        self.client.force_authenticate(user=self.specialist_user)
        response = self.client.get(self.today_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("appointments_by_status", response.data["data"])
        self.assertIn("total_appointments", response.data["data"])

    def test_today_appointments_as_patient_forbidden(self):
        """Test patient cannot access today's appointments endpoint"""
        self.client.force_authenticate(user=self.patient)

        response = self.client.get(self.today_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_today_appointments_unauthenticated(self):
        """Test today's appointments without authentication"""
        response = self.client.get(self.today_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # =============================================
    # Tests for Permissions
    # =============================================

    def test_patient_cannot_update_appointment(self):
        """Test patient cannot update appointment"""
        self.client.force_authenticate(user=self.patient)

        data = {"status": "confirmed"}
        response = self.client.patch(self.detail_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_update_appointment(self):
        """Test admin can update appointment"""
        self.client.force_authenticate(user=self.admin)

        data = {"status": "confirmed"}
        response = self.client.patch(self.detail_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "confirmed")

    # =============================================
    # Tests for Edge Cases
    # =============================================

    def test_list_appointments_empty_queryset(self):
        """Test listing appointments when none exist for user"""
        new_patient = User.objects.create_user(
            email="newpatient@test.com",
            password="testpass123",
            first_name="New",
            last_name="Patient",
            user_type="patient",
        )

        self.client.force_authenticate(user=new_patient)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 0)

    # ERROR ConflictError: Specialist already has an appointment scheduled for this time
    def test_create_appointment_auto_assign_patient(self):
        """Test appointment auto-assigns current user as patient"""
        self.client.force_authenticate(user=self.patient)

        start_time = self.get_valid_appointment_time(days_ahead=10)
        end_time = start_time + timedelta(minutes=30)
        data = {
            "specialist_id": self.specialist.id,
            # No patient_id - should auto-assign
            "appointment_type": "consultation",
            "appointment_date": start_time.date().isoformat(),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_minutes": 30,
        }

        response = self.client.post(self.list_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["patient"], self.patient.id)
