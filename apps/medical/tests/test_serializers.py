"""
Tests for Medical app serializers
"""

from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.medical.models import MedicalRecord
from apps.medical.serializers import (
    MedicalRecordSerializer,
    MedicalRecordCreateSerializer,
    MedicalRecordUpdateSerializer,
    MedicalRecordFilterSerializer,
    MedicalRecordExportSerializer,
    MedicalRecordAuditSerializer,
)
from apps.appointments.models import Appointment
from apps.specialists.models import Specialist

User = get_user_model()


class MedicalRecordSerializerTestCase(TestCase):
    """Test MedicalRecordSerializer (read-only)"""

    def setUp(self):
        """Set up test data"""
        # Create users
        self.patient_user = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            first_name="John",
            last_name="Patient",
            user_type="patient",
        )

        self.specialist_user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            first_name="Dr",
            last_name="Smith",
            user_type="specialist",
        )

        # Create specialist profile
        self.specialist = Specialist.objects.create(
            user=self.specialist_user,
            specialization="Psychiatry",
            license_number="PSY12345",
            years_experience=5,
            consultation_fee=150,
        )

        # Create appointment
        appointment_datetime = timezone.now() - timedelta(hours=2)
        self.appointment = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_date=appointment_datetime,
            start_time=appointment_datetime,
            end_time=appointment_datetime + timedelta(hours=1),
            duration_minutes=60,
            appointment_type="consultation",
            status="completed",
        )

        # Create medical record
        self.medical_record = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Anxiety disorder diagnosis with clinical assessment",
            prescription="Medication A - 10mg daily",
            notes="Patient shows improvement",
            recommendations="Continue therapy sessions",
            follow_up_date=timezone.now().date() + timedelta(days=30),
            confidentiality_level="standard",
        )

    def test_serializer_contains_expected_fields(self):
        """Test serializer contains all expected fields"""
        serializer = MedicalRecordSerializer(instance=self.medical_record)
        data = serializer.data

        expected_fields = {
            "id",
            "patient_id",
            "patient_name",
            "specialist_id",
            "specialist_name",
            "appointment_id",
            "appointment_date",
            "diagnosis",
            "prescription",
            "notes",
            "recommendations",
            "follow_up_date",
            "confidentiality_level",
            "confidentiality_display",
            "created_at",
            "updated_at",
        }

        self.assertEqual(set(data.keys()), expected_fields)

    def test_serializer_field_values(self):
        """Test serializer returns correct field values"""
        serializer = MedicalRecordSerializer(instance=self.medical_record)
        data = serializer.data

        self.assertEqual(data["patient_id"], self.patient_user.id)
        self.assertEqual(data["patient_name"], "John Patient")
        self.assertEqual(data["specialist_id"], self.specialist.id)
        self.assertEqual(data["specialist_name"], "Dr Smith")
        self.assertEqual(data["appointment_id"], self.appointment.id)
        self.assertEqual(data["diagnosis"], self.medical_record.diagnosis)
        self.assertEqual(data["prescription"], self.medical_record.prescription)
        self.assertEqual(data["confidentiality_level"], "standard")

    def test_serializer_with_multiple_records(self):
        """Test serializer with multiple records"""
        # Create another record
        MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Follow-up diagnosis with assessment",
            confidentiality_level="sensitive",
        )

        records = MedicalRecord.objects.all()
        serializer = MedicalRecordSerializer(records, many=True)

        self.assertEqual(len(serializer.data), 2)


class MedicalRecordCreateSerializerTestCase(TestCase):
    """Test MedicalRecordCreateSerializer"""

    def setUp(self):
        """Set up test data"""
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
            specialization="Psychology",
            license_number="PSY67890",
            years_experience=3,
            consultation_fee=120,
        )

        appointment_datetime = timezone.now() - timedelta(hours=1)
        self.appointment = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_date=appointment_datetime,
            start_time=appointment_datetime,
            end_time=appointment_datetime + timedelta(hours=1),
            duration_minutes=60,
            appointment_type="consultation",
            status="completed",
        )

    def test_valid_data(self):
        """Test serializer with valid data"""
        data = {
            "appointment": self.appointment.id,
            "diagnosis": "Depression diagnosis with comprehensive clinical assessment",
            "prescription": "Medication B - 20mg daily",
            "notes": "Patient responsive to treatment",
            "recommendations": "Continue medication for 3 months",
            "follow_up_date": (timezone.now().date() + timedelta(days=14)).isoformat(),
            "confidentiality_level": "standard",
        }

        serializer = MedicalRecordCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(
            serializer.validated_data["appointment"].id, self.appointment.id
        )

    def test_missing_required_fields(self):
        """Test serializer fails with missing required fields"""
        data = {
            "prescription": "Some prescription",
        }

        serializer = MedicalRecordCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("appointment", serializer.errors)
        self.assertIn("diagnosis", serializer.errors)

    def test_diagnosis_too_short(self):
        """Test diagnosis validation fails when too short"""
        data = {
            "appointment": self.appointment.id,
            "diagnosis": "Short",
            "confidentiality_level": "standard",
        }

        serializer = MedicalRecordCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("diagnosis", serializer.errors)
        self.assertIn("at least 10 characters", str(serializer.errors["diagnosis"]))

    def test_diagnosis_strips_whitespace(self):
        """Test diagnosis whitespace is stripped"""
        data = {
            "appointment": self.appointment.id,
            "diagnosis": "  Valid diagnosis with proper assessment  ",
            "confidentiality_level": "standard",
        }

        serializer = MedicalRecordCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(
            serializer.validated_data["diagnosis"],
            "Valid diagnosis with proper assessment",
        )

    def test_prescription_too_short(self):
        """Test prescription validation fails when too short"""
        data = {
            "appointment": self.appointment.id,
            "diagnosis": "Valid diagnosis with assessment",
            "prescription": "Med",
            "confidentiality_level": "standard",
        }

        serializer = MedicalRecordCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("prescription", serializer.errors)

    def test_prescription_optional(self):
        """Test prescription is optional"""
        data = {
            "appointment": self.appointment.id,
            "diagnosis": "Valid diagnosis with assessment",
            "confidentiality_level": "standard",
        }

        serializer = MedicalRecordCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data.get("prescription", ""), "")

    def test_notes_too_short(self):
        """Test notes validation fails when too short"""
        data = {
            "appointment": self.appointment.id,
            "diagnosis": "Valid diagnosis with assessment",
            "notes": "abc",
            "confidentiality_level": "standard",
        }

        serializer = MedicalRecordCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("notes", serializer.errors)

    def test_follow_up_date_in_past(self):
        """Test follow-up date validation fails when in past"""
        data = {
            "appointment": self.appointment.id,
            "diagnosis": "Valid diagnosis with assessment",
            "follow_up_date": (timezone.now().date() - timedelta(days=1)).isoformat(),
            "confidentiality_level": "standard",
        }

        serializer = MedicalRecordCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("follow_up_date", serializer.errors)
        self.assertIn(
            "must be today or a future date.",
            str(serializer.errors["follow_up_date"]),
        )

    def test_appointment_not_found(self):
        """Test validation fails when appointment doesn't exist"""
        data = {
            "appointment": 99999,
            "diagnosis": "Valid diagnosis with assessment",
            "confidentiality_level": "standard",
        }

        serializer = MedicalRecordCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("appointment", serializer.errors)
        self.assertIn("not exist", str(serializer.errors["appointment"]))

    def test_default_confidentiality_level(self):
        """Test default confidentiality level is applied"""
        data = {
            "appointment": self.appointment.id,
            "diagnosis": "Valid diagnosis with assessment",
        }

        serializer = MedicalRecordCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        # Default is set in Meta.extra_kwargs


class MedicalRecordUpdateSerializerTestCase(TestCase):
    """Test MedicalRecordUpdateSerializer"""

    def setUp(self):
        """Set up test data"""
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

        appointment_datetime = timezone.now() - timedelta(hours=1)
        self.appointment = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_date=appointment_datetime,
            start_time=appointment_datetime,
            end_time=appointment_datetime + timedelta(hours=1),
            duration_minutes=60,
            appointment_type="consultation",
            status="completed",
        )

        self.medical_record = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Original diagnosis with assessment",
            confidentiality_level="standard",
        )

    def test_valid_update_data(self):
        """Test serializer with valid update data"""
        data = {
            "diagnosis": "Updated diagnosis with new assessment findings",
            "prescription": "Updated medication - 15mg daily",
            "notes": "Patient shows significant improvement",
        }

        serializer = MedicalRecordUpdateSerializer(
            instance=self.medical_record, data=data, partial=True
        )
        self.assertTrue(serializer.is_valid())

    def test_partial_update(self):
        """Test partial update is allowed"""
        data = {"notes": "Just updating notes"}

        serializer = MedicalRecordUpdateSerializer(
            instance=self.medical_record, data=data, partial=True
        )
        self.assertTrue(serializer.is_valid())

    def test_diagnosis_validation_on_update(self):
        """Test diagnosis validation applies on update"""
        data = {"diagnosis": "Short"}

        serializer = MedicalRecordUpdateSerializer(
            instance=self.medical_record, data=data, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("diagnosis", serializer.errors)

    def test_follow_up_date_validation_on_update(self):
        """Test follow-up date validation on update"""
        data = {"follow_up_date": timezone.now().date() - timedelta(days=5)}

        serializer = MedicalRecordUpdateSerializer(
            instance=self.medical_record, data=data, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("follow_up_date", serializer.errors)

    def test_all_fields_updatable(self):
        """Test all allowed fields can be updated"""
        data = {
            "diagnosis": "Fully updated diagnosis with assessment",
            "prescription": "New prescription - 25mg",
            "notes": "Detailed notes here",
            "recommendations": "New recommendations",
            "follow_up_date": (timezone.now().date() + timedelta(days=30)).isoformat(),
        }

        serializer = MedicalRecordUpdateSerializer(
            instance=self.medical_record, data=data
        )
        self.assertTrue(serializer.is_valid())


class MedicalRecordFilterSerializerTestCase(TestCase):
    """Test MedicalRecordFilterSerializer"""

    def test_valid_filter_data(self):
        """Test serializer with valid filter data"""
        data = {
            "patient_id": 1,
            "specialist_id": 2,
            "confidentiality_level": "standard",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "has_follow_up": True,
            "search": "anxiety",
            "page": 1,
            "page_size": 20,
            "ordering": "-created_at",
        }

        serializer = MedicalRecordFilterSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_all_fields_optional(self):
        """Test all fields are optional"""
        data = {}

        serializer = MedicalRecordFilterSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_default_values(self):
        """Test default values are applied"""
        data = {}

        serializer = MedicalRecordFilterSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["page"], 1)
        self.assertEqual(serializer.validated_data["page_size"], 20)
        self.assertEqual(serializer.validated_data["ordering"], "-created_at")

    def test_page_validation(self):
        """Test page number validation"""
        data = {"page": 0}

        serializer = MedicalRecordFilterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("page", serializer.errors)

    def test_page_size_validation(self):
        """Test page size validation"""
        data = {"page_size": 0}

        serializer = MedicalRecordFilterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("page_size", serializer.errors)

        data = {"page_size": 101}
        serializer = MedicalRecordFilterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("page_size", serializer.errors)

    def test_confidentiality_level_choices(self):
        """Test confidentiality level validates against choices"""
        data = {"confidentiality_level": "invalid_level"}

        serializer = MedicalRecordFilterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("confidentiality_level", serializer.errors)

    def test_ordering_choices(self):
        """Test ordering validates against choices"""
        data = {"ordering": "invalid_field"}

        serializer = MedicalRecordFilterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("ordering", serializer.errors)

    def test_valid_ordering_choices(self):
        """Test all valid ordering choices work"""
        valid_orderings = [
            "created_at",
            "-created_at",
            "follow_up_date",
            "-follow_up_date",
        ]

        for ordering in valid_orderings:
            data = {"ordering": ordering}
            serializer = MedicalRecordFilterSerializer(data=data)
            self.assertTrue(serializer.is_valid())

    def test_search_max_length(self):
        """Test search field max length validation"""
        data = {"search": "a" * 101}

        serializer = MedicalRecordFilterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("search", serializer.errors)


class MedicalRecordExportSerializerTestCase(TestCase):
    """Test MedicalRecordExportSerializer"""

    def test_valid_export_data(self):
        """Test serializer with valid export data"""
        data = {
            "format": "pdf",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "include_prescriptions": True,
            "include_notes": True,
            "patient_id": 1,
        }

        serializer = MedicalRecordExportSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_required_fields(self):
        """Test required fields validation"""
        data = {"format": "pdf"}

        serializer = MedicalRecordExportSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("start_date", serializer.errors)
        self.assertIn("end_date", serializer.errors)

    def test_format_choices(self):
        """Test format validates against choices"""
        data = {
            "format": "xml",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        }

        serializer = MedicalRecordExportSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("format", serializer.errors)

    def test_valid_format_choices(self):
        """Test all valid format choices work"""
        valid_formats = ["pdf", "csv", "json"]

        for fmt in valid_formats:
            data = {
                "format": fmt,
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            }
            serializer = MedicalRecordExportSerializer(data=data)
            self.assertTrue(serializer.is_valid())

    def test_start_date_after_end_date(self):
        """Test validation fails when start date is after end date"""
        data = {
            "format": "pdf",
            "start_date": "2026-01-31",
            "end_date": "2026-01-01",
        }

        serializer = MedicalRecordExportSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)
        self.assertIn("before end date", str(serializer.errors))

    def test_default_values(self):
        """Test default values are applied"""
        data = {
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        }

        serializer = MedicalRecordExportSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["format"], "pdf")
        self.assertEqual(serializer.validated_data["include_prescriptions"], True)
        self.assertEqual(serializer.validated_data["include_notes"], True)

    def test_patient_id_optional(self):
        """Test patient_id is optional"""
        data = {
            "format": "csv",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        }

        serializer = MedicalRecordExportSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertNotIn("patient_id", serializer.validated_data)


class MedicalRecordAuditSerializerTestCase(TestCase):
    """Test MedicalRecordAuditSerializer"""

    def test_valid_audit_data(self):
        """Test serializer with valid audit data"""
        data = {
            "patient_id": 1,
            "specialist_id": 2,
            "action": "view",
            "start_date": "2026-01-01T00:00:00Z",
            "end_date": "2026-01-31T23:59:59Z",
        }

        serializer = MedicalRecordAuditSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_all_fields_optional(self):
        """Test all fields are optional"""
        data = {}

        serializer = MedicalRecordAuditSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_action_choices(self):
        """Test action validates against choices"""
        data = {"action": "invalid_action"}

        serializer = MedicalRecordAuditSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("action", serializer.errors)

    def test_valid_action_choices(self):
        """Test all valid action choices work"""
        valid_actions = ["view", "create", "update", "export"]

        for action in valid_actions:
            data = {"action": action}
            serializer = MedicalRecordAuditSerializer(data=data)
            self.assertTrue(serializer.is_valid())

    def test_start_date_after_end_date(self):
        """Test validation fails when start date is after end date"""
        data = {
            "start_date": "2026-01-31T00:00:00Z",
            "end_date": "2026-01-01T00:00:00Z",
        }

        serializer = MedicalRecordAuditSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)
        self.assertIn("before end date", str(serializer.errors))

    def test_partial_date_range(self):
        """Test validation passes with only start or end date"""
        # Only start date
        data = {"start_date": "2026-01-01T00:00:00Z"}
        serializer = MedicalRecordAuditSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Only end date
        data = {"end_date": "2026-01-31T00:00:00Z"}
        serializer = MedicalRecordAuditSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_datetime_format(self):
        """Test datetime fields accept proper datetime format"""
        data = {
            "start_date": "2026-01-01T10:30:00Z",
            "end_date": "2026-01-31T15:45:00Z",
        }

        serializer = MedicalRecordAuditSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class SerializerEdgeCasesTestCase(TestCase):
    """Test edge cases across serializers"""

    def test_create_serializer_with_empty_strings(self):
        """Test create serializer handles empty strings properly"""
        appointment_datetime = timezone.now() - timedelta(hours=1)
        patient = User.objects.create_user(
            email="patient@test.com", password="pass", user_type="patient"
        )
        specialist_user = User.objects.create_user(
            email="specialist@test.com", password="pass", user_type="specialist"
        )
        specialist = Specialist.objects.create(
            user=specialist_user,
            specialization="Psychology",
            license_number="PSY123",
            years_experience=3,
            consultation_fee=120,
        )
        appointment = Appointment.objects.create(
            patient=patient,
            specialist=specialist,
            appointment_date=appointment_datetime,
            start_time=appointment_datetime,
            end_time=appointment_datetime + timedelta(hours=1),
            duration_minutes=60,
            appointment_type="consultation",
            status="completed",
        )

        data = {
            "appointment_id": appointment.id,
            "diagnosis": "Valid diagnosis with assessment",
            "prescription": "",
            "notes": "",
            "confidentiality_level": "standard",
        }

        serializer = MedicalRecordCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["prescription"], "")
        self.assertEqual(serializer.validated_data["notes"], "")

    def test_filter_serializer_boundary_values(self):
        """Test filter serializer at boundary values"""
        # Minimum page size
        data = {"page_size": 1}
        serializer = MedicalRecordFilterSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Maximum page size
        data = {"page_size": 100}
        serializer = MedicalRecordFilterSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_export_serializer_same_start_end_date(self):
        """Test export serializer with same start and end date"""
        data = {
            "format": "json",
            "start_date": "2026-01-15",
            "end_date": "2026-01-15",
        }

        serializer = MedicalRecordExportSerializer(data=data)
        self.assertTrue(serializer.is_valid())
