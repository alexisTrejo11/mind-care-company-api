"""
Tests for Medical app views
"""

from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.medical.models import MedicalRecord
from apps.appointments.models import Appointment
from apps.specialists.models import Specialist

User = get_user_model()


class MedicalRecordViewSetTestCase(TestCase):
    """Test MedicalRecordViewSet"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create users
        self.admin_user = User.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            first_name="Admin",
            last_name="User",
            user_type="admin",
        )

        self.patient_user = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            first_name="John",
            last_name="Patient",
            user_type="patient",
        )

        self.other_patient_user = User.objects.create_user(
            email="patient2@test.com",
            password="testpass123",
            first_name="Jane",
            last_name="Patient",
            user_type="patient",
        )

        self.specialist_user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            first_name="Dr",
            last_name="Specialist",
            user_type="specialist",
        )

        self.other_specialist_user = User.objects.create_user(
            email="specialist2@test.com",
            password="testpass123",
            first_name="Dr",
            last_name="Other",
            user_type="specialist",
        )

        self.staff_user = User.objects.create_user(
            email="staff@test.com",
            password="testpass123",
            first_name="Staff",
            last_name="User",
            user_type="staff",
        )

        # Create specialist profiles
        self.specialist = Specialist.objects.create(
            user=self.specialist_user,
            specialization="Psychiatry",
            license_number="PSY12345",
            years_experience=5,
            consultation_fee=150,
        )

        self.other_specialist = Specialist.objects.create(
            user=self.other_specialist_user,
            specialization="Psychology",
            license_number="PSY67890",
            years_experience=3,
            consultation_fee=120,
        )

        # Create appointments
        appointment_datetime = timezone.now() - timedelta(hours=2)
        self.appointment = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_date=appointment_datetime.date(),
            start_time=appointment_datetime,
            end_time=appointment_datetime + timedelta(hours=1),
            duration_minutes=60,
            appointment_type="consultation",
            status="completed",
        )

        self.other_appointment = Appointment.objects.create(
            patient=self.other_patient_user,
            specialist=self.other_specialist,
            appointment_date=appointment_datetime.date(),
            start_time=appointment_datetime,
            end_time=appointment_datetime + timedelta(hours=1),
            duration_minutes=60,
            appointment_type="consultation",
            status="completed",
        )

        # Create medical records
        self.medical_record = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Anxiety disorder diagnosis with clinical assessment",
            prescription="Medication A - 10mg daily",
            notes="Patient shows improvement",
            confidentiality_level="standard",
        )

        self.other_medical_record = MedicalRecord.objects.create(
            patient=self.other_patient_user,
            specialist=self.other_specialist,
            appointment=self.other_appointment,
            diagnosis="Depression diagnosis with clinical assessment",
            confidentiality_level="standard",
        )

        self.base_url = "/api/v2/medical-records/"

    # ==================== List Tests ====================

    def test_list_records_as_admin(self):
        """Test admin can list all records"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.base_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["data"]), 2)

    def test_list_records_as_patient(self):
        """Test patient can only see their own records"""
        self.client.force_authenticate(user=self.patient_user)
        response = self.client.get(self.base_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["patient_id"], self.patient_user.id)

    def test_list_records_as_specialist(self):
        """Test specialist can only see their own records"""
        self.client.force_authenticate(user=self.specialist_user)
        response = self.client.get(self.base_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["specialist_id"], self.specialist.id)

    def test_list_records_as_staff(self):
        """Test staff can only see standard confidentiality records"""
        # Create a sensitive record
        MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Sensitive diagnosis with assessment",
            confidentiality_level="sensitive",
        )

        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(self.base_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see standard records
        for record in response.data["data"]:
            self.assertEqual(record["confidentiality_level"], "standard")

    def test_list_records_unauthenticated(self):
        """Test unauthenticated user cannot list records"""
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_records_with_filters(self):
        """Test listing records with filters"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.base_url, {"patient_id": self.patient_user.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for record in response.data["data"]:
            self.assertEqual(record["patient_id"], self.patient_user.id)

    def test_list_records_with_search(self):
        """Test listing records with search"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.base_url, {"search": "anxiety"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["data"]), 1)

    # ==================== Retrieve Tests ====================

    def test_retrieve_record_as_owner(self):
        """Test patient can retrieve their own record"""
        self.client.force_authenticate(user=self.patient_user)
        url = f"{self.base_url}{self.medical_record.id}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["id"], self.medical_record.id)
        self.assertIn("can_edit", response.data["data"])
        self.assertIn("can_delete", response.data["data"])

    def test_retrieve_record_as_specialist(self):
        """Test specialist can retrieve their own record"""
        self.client.force_authenticate(user=self.specialist_user)
        url = f"{self.base_url}{self.medical_record.id}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["id"], self.medical_record.id)

    def test_retrieve_record_unauthorized(self):
        """Test user cannot retrieve another user's record"""
        self.client.force_authenticate(user=self.other_patient_user)
        url = f"{self.base_url}{self.medical_record.id}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_record_not_found(self):
        """Test retrieve non-existent record"""
        self.client.force_authenticate(user=self.admin_user)
        url = f"{self.base_url}99999/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================== Create Tests ====================

    def test_create_record_as_specialist(self):
        """Test specialist can create medical record"""
        # Create new appointment
        appointment_datetime = timezone.now() - timedelta(hours=1)
        new_appointment = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_date=appointment_datetime.date(),
            start_time=appointment_datetime,
            end_time=appointment_datetime + timedelta(hours=1),
            duration_minutes=60,
            appointment_type="consultation",
            status="completed",
        )

        self.client.force_authenticate(user=self.specialist_user)
        data = {
            "appointment_id": new_appointment.id,
            "diagnosis": "New diagnosis with comprehensive assessment",
            "prescription": "Medication C - 15mg daily",
            "notes": "Initial consultation notes",
            "confidentiality_level": "standard",
        }

        response = self.client.post(self.base_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["diagnosis"], data["diagnosis"])

    def test_create_record_as_admin(self):
        """Test admin can create medical record"""
        appointment_datetime = timezone.now() - timedelta(hours=1)
        new_appointment = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_date=appointment_datetime.date(),
            start_time=appointment_datetime,
            end_time=appointment_datetime + timedelta(hours=1),
            duration_minutes=60,
            appointment_type="consultation",
            status="completed",
        )

        self.client.force_authenticate(user=self.admin_user)
        data = {
            "appointment_id": new_appointment.id,
            "diagnosis": "Admin created diagnosis with assessment",
            "confidentiality_level": "standard",
        }

        response = self.client.post(self.base_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_record_as_patient_fails(self):
        """Test patient cannot create medical record"""
        self.client.force_authenticate(user=self.patient_user)
        data = {
            "appointment_id": self.appointment.id,
            "diagnosis": "Patient diagnosis with assessment",
            "confidentiality_level": "standard",
        }

        response = self.client.post(self.base_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_record_validation_error(self):
        """Test create record with validation errors"""
        self.client.force_authenticate(user=self.specialist_user)
        data = {
            "appointment_id": self.appointment.id,
            "diagnosis": "Short",  # Too short
            "confidentiality_level": "standard",
        }

        response = self.client.post(self.base_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ==================== Update Tests ====================

    def test_update_record_as_admin(self):
        """Test admin can update any record"""
        self.client.force_authenticate(user=self.admin_user)
        url = f"{self.base_url}{self.medical_record.id}/"
        data = {
            "diagnosis": "Updated diagnosis with new assessment findings",
            "notes": "Updated notes",
        }

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Updated", response.data["data"]["diagnosis"])

    def test_update_record_as_specialist_within_window(self):
        """Test specialist can update their own record within edit window"""
        # Create fresh record
        fresh_record = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Fresh diagnosis with assessment",
            confidentiality_level="standard",
        )

        self.client.force_authenticate(user=self.specialist_user)
        url = f"{self.base_url}{fresh_record.id}/"
        data = {"notes": "Updated notes"}

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_record_unauthorized(self):
        """Test user cannot update unauthorized record"""
        self.client.force_authenticate(user=self.patient_user)
        url = f"{self.base_url}{self.medical_record.id}/"
        data = {"notes": "Attempted update"}

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== Delete Tests ====================

    def test_delete_record_as_admin(self):
        """Test admin can delete record"""
        record_to_delete = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Record to delete with assessment",
            confidentiality_level="standard",
        )

        self.client.force_authenticate(user=self.admin_user)
        url = f"{self.base_url}{record_to_delete.id}/"
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(MedicalRecord.objects.filter(id=record_to_delete.id).exists())

    def test_delete_record_as_specialist_fails(self):
        """Test specialist cannot delete record"""
        self.client.force_authenticate(user=self.specialist_user)
        url = f"{self.base_url}{self.medical_record.id}/"
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_record_as_patient_fails(self):
        """Test patient cannot delete record"""
        self.client.force_authenticate(user=self.patient_user)
        url = f"{self.base_url}{self.medical_record.id}/"
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== Patient Records Action Tests ====================

    def test_patient_records_action_as_patient(self):
        """Test patient can get their own records"""
        self.client.force_authenticate(user=self.patient_user)
        url = f"{self.base_url}patient-records/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["data"]), 1)

    def test_patient_records_action_as_non_patient_fails(self):
        """Test non-patient cannot access patient-records endpoint"""
        self.client.force_authenticate(user=self.specialist_user)
        url = f"{self.base_url}patient-records/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== Upcoming Follow-ups Action Tests ====================

    def test_upcoming_follow_ups_action(self):
        """Test upcoming follow-ups action"""
        # Create record with follow-up
        MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Diagnosis with assessment and follow-up",
            follow_up_date=timezone.now().date() + timedelta(days=15),
            confidentiality_level="standard",
        )

        self.client.force_authenticate(user=self.specialist_user)
        url = f"{self.base_url}upcoming-follow-ups/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("summary", response.data["data"])
        self.assertIn("records", response.data["data"])

    def test_upcoming_follow_ups_filters_by_specialist(self):
        """Test follow-ups are filtered by specialist"""
        # Create follow-up for this specialist
        MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Follow-up diagnosis with assessment",
            follow_up_date=timezone.now().date() + timedelta(days=10),
            confidentiality_level="standard",
        )

        self.client.force_authenticate(user=self.specialist_user)
        url = f"{self.base_url}upcoming-follow-ups/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see their own follow-ups
        for record in response.data["data"]["records"]:
            self.assertEqual(record["specialist_id"], self.specialist.id)

    # ==================== Stats Action Tests ====================

    def test_stats_action_as_admin(self):
        """Test admin can get statistics"""
        self.client.force_authenticate(user=self.admin_user)
        url = f"{self.base_url}stats/"
        response = self.client.get(url, {"period": "month"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_records", response.data["data"])
        self.assertIn("confidentiality_distribution", response.data["data"])

    def test_stats_action_as_specialist(self):
        """Test specialist can get their own statistics"""
        self.client.force_authenticate(user=self.specialist_user)
        url = f"{self.base_url}stats/"
        response = self.client.get(url, {"period": "week"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_records", response.data["data"])

    def test_stats_action_as_patient_fails(self):
        """Test patient cannot get statistics"""
        self.client.force_authenticate(user=self.patient_user)
        url = f"{self.base_url}stats/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== Change Confidentiality Action Tests ====================

    def test_change_confidentiality_as_admin(self):
        """Test admin can change confidentiality level"""
        self.client.force_authenticate(user=self.admin_user)
        url = f"{self.base_url}{self.medical_record.id}/change-confidentiality/"
        data = {"confidentiality_level": "sensitive"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["confidentiality_level"], "sensitive")

    def test_change_confidentiality_as_non_admin_fails(self):
        """Test non-admin cannot change confidentiality level"""
        self.client.force_authenticate(user=self.specialist_user)
        url = f"{self.base_url}{self.medical_record.id}/change-confidentiality/"
        data = {"confidentiality_level": "sensitive"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_change_confidentiality_invalid_level(self):
        """Test change confidentiality with invalid level"""
        self.client.force_authenticate(user=self.admin_user)
        url = f"{self.base_url}{self.medical_record.id}/change-confidentiality/"
        data = {"confidentiality_level": "invalid_level"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ==================== Export Records Action Tests ====================

    def test_export_records_as_admin(self):
        """Test admin can export records"""
        self.client.force_authenticate(user=self.admin_user)
        url = f"{self.base_url}export/"
        data = {
            "format": "pdf",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "include_prescriptions": True,
            "include_notes": True,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("format", response.data["data"])
        self.assertIn("record_count", response.data["data"])

    def test_export_records_different_formats(self):
        """Test export in different formats"""
        self.client.force_authenticate(user=self.admin_user)
        url = f"{self.base_url}export/"

        for fmt in ["pdf", "csv", "json"]:
            data = {
                "format": fmt,
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            }
            response = self.client.post(url, data, format="json")

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["data"]["format"], fmt)

    def test_export_records_with_patient_filter(self):
        """Test export with patient filter"""
        self.client.force_authenticate(user=self.admin_user)
        url = f"{self.base_url}export/"
        data = {
            "format": "json",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "patient_id": self.patient_user.id,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_export_records_validation_error(self):
        """Test export with validation error"""
        self.client.force_authenticate(user=self.admin_user)
        url = f"{self.base_url}export/"
        data = {
            "format": "pdf",
            # Missing required dates
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ==================== Audit Log Action Tests ====================

    def test_audit_log_as_admin(self):
        """Test admin can access audit log"""
        self.client.force_authenticate(user=self.admin_user)
        url = f"{self.base_url}audit-log/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("logs", response.data["data"])

    def test_audit_log_with_filters(self):
        """Test audit log with filters"""
        self.client.force_authenticate(user=self.admin_user)
        url = f"{self.base_url}audit-log/"
        params = {
            "action": "view",
            "patient_id": self.patient_user.id,
        }
        response = self.client.get(url, params)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_audit_log_as_non_admin_fails(self):
        """Test non-admin cannot access audit log"""
        self.client.force_authenticate(user=self.specialist_user)
        url = f"{self.base_url}audit-log/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class MedicalRecordViewSetEdgeCasesTestCase(TestCase):
    """Test edge cases and boundary conditions"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        self.admin_user = User.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            user_type="admin",
        )

        self.patient_user = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            user_type="patient",
        )

        self.specialist_user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            user_type="specialist",
        )

        self.specialist = Specialist.objects.create(
            user=self.specialist_user,
            specialization="Psychiatry",
            license_number="PSY12345",
            years_experience=5,
            consultation_fee=150,
        )

        appointment_datetime = timezone.now() - timedelta(hours=2)
        self.appointment = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_date=appointment_datetime.date(),
            start_time=appointment_datetime,
            end_time=appointment_datetime + timedelta(hours=1),
            duration_minutes=60,
            appointment_type="consultation",
            status="completed",
        )

        self.base_url = "/api/v2/medical-records/"

    def test_patient_cannot_see_highly_sensitive_records(self):
        """Test patient cannot see highly sensitive records"""
        # Create highly sensitive record
        highly_sensitive_record = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Highly sensitive diagnosis with assessment",
            confidentiality_level="highly_sensitive",
        )

        self.client.force_authenticate(user=self.patient_user)
        response = self.client.get(self.base_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should not see the highly sensitive record
        record_ids = [r["id"] for r in response.data["data"]]
        self.assertNotIn(highly_sensitive_record.id, record_ids)

    def test_list_with_pagination(self):
        """Test list with pagination"""
        # Create multiple records
        for i in range(5):
            MedicalRecord.objects.create(
                patient=self.patient_user,
                specialist=self.specialist,
                appointment=self.appointment,
                diagnosis=f"Diagnosis {i} with assessment",
                confidentiality_level="standard",
            )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.base_url, {"page_size": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check pagination exists
        # TODO

    def test_empty_queryset(self):
        """Test list returns empty when no records match"""
        self.client.force_authenticate(user=self.patient_user)
        # Delete all records for this patient
        MedicalRecord.objects.filter(patient=self.patient_user).delete()

        response = self.client.get(self.base_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 0)

    def test_invalid_date_format_in_export(self):
        """Test export with invalid date format"""
        self.client.force_authenticate(user=self.admin_user)
        url = f"{self.base_url}export/"
        data = {
            "format": "pdf",
            "start_date": "invalid-date",
            "end_date": "2026-12-31",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
