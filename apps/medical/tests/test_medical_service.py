"""
Tests for MedicalRecordService business logic
"""

import pytest
from datetime import timedelta, date
from django.utils import timezone
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.medical.models import MedicalRecord
from apps.medical.services import MedicalRecordService
from apps.appointments.models import Appointment
from apps.specialists.models import Specialist
from apps.core.exceptions.base_exceptions import (
    BusinessRuleError,
    ValidationError,
    NotFoundError,
    AuthorizationError,
)

User = get_user_model()


class MedicalRecordServiceTestCase(TestCase):
    """Test cases for MedicalRecordService"""

    def setUp(self):
        """Set up test data"""
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
            first_name="Patient",
            last_name="User",
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
            email="other_specialist@test.com",
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

        # Create appointment
        appointment_datetime = timezone.now() - timedelta(days=1)
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

        # Create medical record
        self.medical_record = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Test diagnosis with assessment findings for mental health condition",
            prescription="Medication A - 10mg daily",
            notes="Patient shows improvement",
            confidentiality_level="standard",
        )

    # ==================== Access Control Tests ====================

    def test_admin_can_access_any_record(self):
        """Test admin can access any medical record"""
        result = MedicalRecordService.can_access_record(
            self.admin_user, self.medical_record
        )
        self.assertTrue(result)

    def test_patient_can_access_own_standard_record(self):
        """Test patient can access their own standard records"""
        result = MedicalRecordService.can_access_record(
            self.patient_user, self.medical_record
        )
        self.assertTrue(result)

    def test_patient_cannot_access_highly_sensitive_record(self):
        """Test patient cannot access highly sensitive records"""
        self.medical_record.confidentiality_level = "highly_sensitive"
        self.medical_record.save()

        result = MedicalRecordService.can_access_record(
            self.patient_user, self.medical_record
        )
        self.assertFalse(result)

    def test_specialist_can_access_own_record(self):
        """Test specialist can access records they created"""
        result = MedicalRecordService.can_access_record(
            self.specialist_user, self.medical_record
        )
        self.assertTrue(result)

    def test_specialist_cannot_access_other_specialist_record(self):
        """Test specialist cannot access another specialist's records"""
        result = MedicalRecordService.can_access_record(
            self.other_specialist_user, self.medical_record
        )
        self.assertFalse(result)

    def test_staff_can_access_standard_record(self):
        """Test staff can access standard records"""
        result = MedicalRecordService.can_access_record(
            self.staff_user, self.medical_record
        )
        self.assertTrue(result)

    def test_staff_cannot_access_sensitive_record(self):
        """Test staff cannot access sensitive records"""
        self.medical_record.confidentiality_level = "sensitive"
        self.medical_record.save()

        result = MedicalRecordService.can_access_record(
            self.staff_user, self.medical_record
        )
        self.assertFalse(result)

    def test_unauthenticated_user_cannot_access(self):
        """Test unauthenticated user cannot access records"""
        result = MedicalRecordService.can_access_record(None, self.medical_record)
        self.assertFalse(result)

    # ==================== Edit Permission Tests ====================

    def test_admin_can_always_edit(self):
        """Test admin can always edit records"""
        result = MedicalRecordService.can_edit_record(
            self.admin_user, self.medical_record
        )
        self.assertTrue(result)

    def test_specialist_can_edit_within_window(self):
        """Test specialist can edit within edit window"""
        # Create fresh record (within edit window)
        fresh_record = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Fresh diagnosis with assessment",
            confidentiality_level="standard",
        )

        result = MedicalRecordService.can_edit_record(
            self.specialist_user, fresh_record
        )
        self.assertTrue(result)

    def test_patient_cannot_edit_record(self):
        """Test patient cannot edit medical records"""
        result = MedicalRecordService.can_edit_record(
            self.patient_user, self.medical_record
        )
        self.assertFalse(result)

    # ==================== Delete Permission Tests ====================

    def test_only_admin_can_delete(self):
        """Test only admin can delete medical records"""
        # Admin can delete today's record
        today_record = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Today's diagnosis with assessment",
            confidentiality_level="standard",
        )

        result = MedicalRecordService.can_delete_record(self.admin_user, today_record)
        self.assertTrue(result)

        # Specialist cannot delete
        result = MedicalRecordService.can_delete_record(
            self.specialist_user, today_record
        )
        self.assertFalse(result)

    # ==================== Validation Tests ====================

    def test_validate_record_creation_success(self):
        """Test successful record creation validation"""
        appointment_datetime = timezone.now() - timedelta(hours=2)
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

        # Should not raise exception
        MedicalRecordService.validate_record_creation(
            self.specialist_user, new_appointment
        )

    def test_validate_record_creation_not_completed(self):
        """Test validation fails for non-completed appointment"""
        future_datetime = timezone.now() + timedelta(days=1)
        pending_appointment = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_date=future_datetime.date(),
            start_time=future_datetime,
            end_time=future_datetime + timedelta(hours=1),
            duration_minutes=60,
            appointment_type="consultation",
            status="scheduled",
        )

        with self.assertRaises(BusinessRuleError) as context:
            MedicalRecordService.validate_record_creation(
                self.specialist_user, pending_appointment
            )
        self.assertIn("completed appointments", str(context.exception))

    def test_validate_record_creation_duplicate(self):
        """Test validation fails for duplicate record"""
        with self.assertRaises(BusinessRuleError) as context:
            MedicalRecordService.validate_record_creation(
                self.specialist_user, self.appointment
            )
        self.assertIn("already exists", str(context.exception))

    def test_validate_record_creation_wrong_specialist(self):
        """Test validation fails when specialist doesn't match"""
        appointment_datetime = timezone.now() - timedelta(hours=1)
        new_appointment = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.other_specialist,
            appointment_date=appointment_datetime.date(),
            start_time=appointment_datetime,
            end_time=appointment_datetime + timedelta(hours=1),
            duration_minutes=60,
            appointment_type="consultation",
            status="completed",
        )

        with self.assertRaises(AuthorizationError) as context:
            MedicalRecordService.validate_record_creation(
                self.specialist_user, new_appointment
            )
        self.assertIn("your own appointments", str(context.exception))

    def test_validate_diagnosis_too_short(self):
        """Test diagnosis validation fails when too short"""
        with self.assertRaises(ValidationError) as context:
            MedicalRecordService.validate_diagnosis_content("Short")
        self.assertIn("at least", str(context.exception))

    def test_validate_diagnosis_missing_keywords(self):
        """Test diagnosis validation fails without required keywords"""
        with self.assertRaises(BusinessRuleError) as context:
            MedicalRecordService.validate_diagnosis_content(
                "This is a long text but missing required keywords for medical record"
            )
        self.assertIn("assessment findings", str(context.exception))

    def test_validate_diagnosis_success(self):
        """Test successful diagnosis validation"""
        diagnosis = (
            "Patient presents with anxiety diagnosis and assessment shows improvement"
        )
        result = MedicalRecordService.validate_diagnosis_content(diagnosis)
        self.assertEqual(result, diagnosis)

    def test_validate_prescription_dangerous_combination(self):
        """Test prescription validation detects dangerous combinations"""
        with self.assertRaises(BusinessRuleError) as context:
            MedicalRecordService.validate_prescription_content(
                "Prescribe opioid 10mg and benzodiazepine 5mg"
            )
        self.assertIn("Dangerous drug combination", str(context.exception))

    def test_validate_prescription_success(self):
        """Test successful prescription validation"""
        prescription = "Medication A - 10mg daily"
        result = MedicalRecordService.validate_prescription_content(prescription)
        self.assertEqual(result, prescription)

    def test_validate_follow_up_date_before_appointment(self):
        """Test follow-up date validation fails when before appointment"""
        with self.assertRaises(ValidationError) as context:
            MedicalRecordService.validate_follow_up_date(
                date.today() - timedelta(days=1), timezone.now()
            )
        self.assertIn("after appointment date", str(context.exception))

    def test_validate_follow_up_date_too_soon(self):
        """Test follow-up date validation fails when too soon"""
        appointment_date = timezone.now()
        follow_up = appointment_date.date()  # Same day

        with self.assertRaises(ValidationError) as context:
            MedicalRecordService.validate_follow_up_date(follow_up, appointment_date)
        self.assertIn("after appointment date", str(context.exception))

    def test_validate_follow_up_date_too_far(self):
        """Test follow-up date validation fails when more than a year"""
        appointment_date = timezone.now()
        follow_up = appointment_date.date() + timedelta(days=400)

        with self.assertRaises(ValidationError) as context:
            MedicalRecordService.validate_follow_up_date(follow_up, appointment_date)
        self.assertIn("more than 1 year", str(context.exception))

    def test_validate_confidentiality_level_highly_sensitive(self):
        """Test highly sensitive level requires sensitive content"""
        with self.assertRaises(BusinessRuleError) as context:
            MedicalRecordService.validate_confidentiality_level(
                "highly_sensitive", "Regular diagnosis"
            )
        self.assertIn("sensitive health information", str(context.exception))

    def test_validate_confidentiality_level_with_sensitive_content(self):
        """Test highly sensitive level validation succeeds with sensitive content"""
        result = MedicalRecordService.validate_confidentiality_level(
            "highly_sensitive", "Patient diagnosed with HIV and mental health issues"
        )
        self.assertEqual(result, "highly_sensitive")

    # ==================== Create Medical Record Tests ====================

    def test_create_medical_record_success(self):
        """Test successful medical record creation"""
        appointment_datetime = timezone.now() - timedelta(hours=3)
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

        record = MedicalRecordService.create_medical_record(
            user=self.specialist_user,
            appointment_id=new_appointment.id,
            diagnosis="Patient shows anxiety diagnosis with assessment of moderate severity",
            prescription="Medication B - 20mg daily",
            notes="Follow up in 2 weeks",
            confidentiality_level="standard",
        )

        self.assertIsNotNone(record.id)
        self.assertEqual(record.patient, self.patient_user)
        self.assertEqual(record.specialist, self.specialist)
        self.assertEqual(record.confidentiality_level, "standard")

    def test_create_medical_record_with_follow_up(self):
        """Test creating medical record with follow-up date"""
        appointment_datetime = timezone.now() - timedelta(hours=4)
        new_appointment = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment_date=appointment_datetime.date(),
            start_time=appointment_datetime,
            duration_minutes=60,
            appointment_type="consultation",
            status="completed",
        )

        follow_up = timezone.now().date() + timedelta(days=14)

        record = MedicalRecordService.create_medical_record(
            user=self.specialist_user,
            appointment_id=new_appointment.id,
            diagnosis="Depression diagnosis with clinical assessment completed",
            follow_up_date=follow_up,
            confidentiality_level="standard",
        )

        self.assertEqual(record.follow_up_date, follow_up)

    def test_create_medical_record_appointment_not_found(self):
        """Test creation fails when appointment doesn't exist"""
        with self.assertRaises(NotFoundError) as context:
            MedicalRecordService.create_medical_record(
                user=self.specialist_user,
                appointment_id=99999,
                diagnosis="Test diagnosis with assessment",
                confidentiality_level="standard",
            )
        self.assertIn("not found", str(context.exception))

    # ==================== Update Medical Record Tests ====================

    def test_update_medical_record_success(self):
        """Test successful medical record update"""
        fresh_record = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Initial diagnosis with assessment",
            confidentiality_level="standard",
        )

        updated_record = MedicalRecordService.update_medical_record(
            user=self.admin_user,
            medical_record=fresh_record,
            diagnosis="Updated diagnosis with new assessment findings",
            notes="Additional notes added",
        )

        self.assertIn("Updated", updated_record.diagnosis)
        self.assertEqual(updated_record.notes, "Additional notes added")

    def test_update_medical_record_unauthorized(self):
        """Test update fails when user unauthorized"""
        with self.assertRaises(AuthorizationError) as context:
            MedicalRecordService.update_medical_record(
                user=self.patient_user,
                medical_record=self.medical_record,
                diagnosis="Attempted update",
            )
        self.assertIn("permission", str(context.exception))

    # ==================== Delete Medical Record Tests ====================

    def test_delete_medical_record_success(self):
        """Test successful medical record deletion"""
        record_to_delete = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Record to delete with assessment",
            confidentiality_level="standard",
        )

        record_id = record_to_delete.id

        MedicalRecordService.delete_medical_record(
            user=self.admin_user, medical_record=record_to_delete
        )

        self.assertFalse(MedicalRecord.objects.filter(id=record_id).exists())

    def test_delete_medical_record_unauthorized(self):
        """Test deletion fails when user unauthorized"""
        with self.assertRaises(AuthorizationError) as context:
            MedicalRecordService.delete_medical_record(
                user=self.specialist_user, medical_record=self.medical_record
            )
        self.assertIn("admin", str(context.exception).lower())

    # ==================== Statistics Tests ====================

    def test_get_statistics_success(self):
        """Test getting statistics successfully"""
        stats = MedicalRecordService.get_statistics(
            user=self.admin_user, period="month"
        )

        self.assertIn("total_records", stats)
        self.assertIn("confidentiality_distribution", stats)
        self.assertIn("follow_up_stats", stats)
        self.assertGreaterEqual(stats["total_records"], 1)

    def test_get_statistics_unauthorized(self):
        """Test statistics fails for unauthorized user"""
        with self.assertRaises(AuthorizationError) as context:
            MedicalRecordService.get_statistics(user=self.patient_user, period="month")
        self.assertIn("admin, staff, or specialists", str(context.exception))

    def test_get_statistics_specialist_sees_own_only(self):
        """Test specialist sees only their own records in statistics"""
        # Create record for other specialist
        appointment_datetime = timezone.now() - timedelta(hours=5)
        other_appointment = Appointment.objects.create(
            patient=self.patient_user,
            specialist=self.other_specialist,
            appointment_date=appointment_datetime.date(),
            start_time=appointment_datetime,
            duration_minutes=60,
            appointment_type="consultation",
            status="completed",
        )

        MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.other_specialist,
            appointment=other_appointment,
            diagnosis="Other specialist diagnosis with assessment",
            confidentiality_level="standard",
        )

        stats = MedicalRecordService.get_statistics(
            user=self.specialist_user, period="month"
        )

        # Should only see their own record count
        self.assertEqual(stats["total_records"], 1)


class MedicalRecordServiceEdgeCasesTestCase(TestCase):
    """Test edge cases and boundary conditions"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            user_type="admin",
        )

    def test_validate_diagnosis_exactly_min_length(self):
        """Test diagnosis validation at minimum length boundary"""
        min_diagnosis = "diagnosis1"  # 10 characters

        result = MedicalRecordService.validate_diagnosis_content(min_diagnosis)
        self.assertEqual(result, min_diagnosis)

    def test_validate_follow_up_date_exactly_one_day(self):
        """Test follow-up date validation at minimum boundary"""
        appointment_date = timezone.now()
        follow_up = appointment_date.date() + timedelta(days=1)

        result = MedicalRecordService.validate_follow_up_date(
            follow_up, appointment_date
        )
        self.assertEqual(result, follow_up)

    def test_validate_follow_up_date_exactly_one_year(self):
        """Test follow-up date validation at maximum boundary"""
        appointment_date = timezone.now()
        follow_up = appointment_date.date() + timedelta(days=365)

        result = MedicalRecordService.validate_follow_up_date(
            follow_up, appointment_date
        )
        self.assertEqual(result, follow_up)

    def test_empty_prescription_is_valid(self):
        """Test empty prescription is allowed"""
        result = MedicalRecordService.validate_prescription_content("")
        self.assertEqual(result, "")

    def test_none_follow_up_date_returns_none(self):
        """Test None follow-up date is allowed"""
        result = MedicalRecordService.validate_follow_up_date(None, timezone.now())
        self.assertIsNone(result)
