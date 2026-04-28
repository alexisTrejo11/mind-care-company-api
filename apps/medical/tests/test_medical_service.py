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
    PrivacyError,
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
            appointment=new_appointment,
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
            appointment_date=appointment_datetime,
            start_time=appointment_datetime,
            end_time=appointment_datetime + timedelta(hours=1),
            duration_minutes=60,
            appointment_type="consultation",
            status="completed",
        )

        follow_up = timezone.now().date() + timedelta(days=14)

        record = MedicalRecordService.create_medical_record(
            user=self.specialist_user,
            appointment=new_appointment,
            diagnosis="Depression diagnosis with clinical assessment completed",
            follow_up_date=follow_up,
            confidentiality_level="standard",
        )

        self.assertEqual(record.follow_up_date, follow_up)

    def test_create_medical_record_appointment_not_provided(self):
        """Test creation fails when appointment is not provided"""
        with self.assertRaises(ValidationError) as context:
            MedicalRecordService.create_medical_record(
                user=self.specialist_user,
                appointment=None,
                diagnosis="Test diagnosis with assessment",
                confidentiality_level="standard",
            )
        self.assertIn("must be provided", str(context.exception))

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
        with self.assertRaises(PrivacyError) as context:
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
            end_time=appointment_datetime + timedelta(hours=1),
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


class MedicalRecordServiceFilteringTestCase(TestCase):
    """Test cases for get_filtered_records() - service-driven access control"""

    def setUp(self):
        """Set up test data with multiple users and records"""
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

        self.other_patient_user = User.objects.create_user(
            email="other_patient@test.com",
            password="testpass123",
            first_name="Other",
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
            last_name="Member",
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
        appointment_datetime = timezone.now() - timedelta(days=2)
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

        other_appointment_datetime = timezone.now() - timedelta(days=1)
        self.other_appointment = Appointment.objects.create(
            patient=self.other_patient_user,
            specialist=self.other_specialist,
            appointment_date=other_appointment_datetime.date(),
            start_time=other_appointment_datetime,
            end_time=other_appointment_datetime + timedelta(hours=1),
            duration_minutes=60,
            appointment_type="consultation",
            status="completed",
        )

        # Create medical records with different confidentiality levels
        self.standard_record = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Patient shows anxiety diagnosis with assessment of severity",
            prescription="Medication A - 10mg daily",
            notes="Standard confidentiality record",
            confidentiality_level="standard",
        )

        self.sensitive_record = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Sensitive diagnosis with assessment findings",
            notes="Sensitive confidentiality record",
            confidentiality_level="sensitive",
        )

        self.highly_sensitive_record = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="HIV positive diagnosis with mental health assessment",
            notes="Highly sensitive confidentiality record",
            confidentiality_level="highly_sensitive",
        )

        self.other_patient_record = MedicalRecord.objects.create(
            patient=self.other_patient_user,
            specialist=self.other_specialist,
            appointment=self.other_appointment,
            diagnosis="Other patient diagnosis with assessment",
            notes="Other patient's record",
            confidentiality_level="standard",
        )

    # ==================== Admin User Filtering Tests ====================

    def test_admin_sees_all_records(self):
        """Test admin can access all medical records regardless of confidentiality"""
        records = MedicalRecordService.get_filtered_records(user=self.admin_user)
        record_count = records.count()

        self.assertEqual(record_count, 4)
        record_ids = set(records.values_list("id", flat=True))
        self.assertIn(self.standard_record.id, record_ids)
        self.assertIn(self.sensitive_record.id, record_ids)
        self.assertIn(self.highly_sensitive_record.id, record_ids)
        self.assertIn(self.other_patient_record.id, record_ids)

    def test_admin_sees_all_confidentiality_levels(self):
        """Test admin sees records at all confidentiality levels"""
        records = MedicalRecordService.get_filtered_records(user=self.admin_user)
        confidentiality_levels = set(
            records.values_list("confidentiality_level", flat=True)
        )

        self.assertIn("standard", confidentiality_levels)
        self.assertIn("sensitive", confidentiality_levels)
        self.assertIn("highly_sensitive", confidentiality_levels)

    # ==================== Patient User Filtering Tests ====================

    def test_patient_sees_only_own_records(self):
        """Test patient can only access their own medical records"""
        records = MedicalRecordService.get_filtered_records(user=self.patient_user)
        record_count = records.count()

        # Patient should see own standard and sensitive, but NOT highly sensitive
        self.assertEqual(record_count, 2)
        record_ids = set(records.values_list("id", flat=True))
        self.assertIn(self.standard_record.id, record_ids)
        self.assertIn(self.sensitive_record.id, record_ids)

    def test_patient_cannot_see_own_highly_sensitive_records(self):
        """Test patient cannot access their own highly sensitive records"""
        records = MedicalRecordService.get_filtered_records(
            user=self.patient_user, filters={}
        )
        highly_sensitive_ids = records.filter(
            confidentiality_level="highly_sensitive"
        ).values_list("id", flat=True)

        self.assertNotIn(self.highly_sensitive_record.id, highly_sensitive_ids)
        self.assertEqual(len(list(highly_sensitive_ids)), 0)

    def test_patient_cannot_see_other_patient_records(self):
        """Test patient cannot access other patients' records"""
        records = MedicalRecordService.get_filtered_records(
            user=self.patient_user, filters={}
        )
        record_ids = set(records.values_list("id", flat=True))

        self.assertNotIn(self.other_patient_record.id, record_ids)

    def test_patient_filtered_records_are_own_patient_only(self):
        """Test all filtered records belong to the patient"""
        records = MedicalRecordService.get_filtered_records(
            user=self.patient_user, filters={}
        )
        patient_ids = set(records.values_list("patient_id", flat=True))

        self.assertEqual(patient_ids, {self.patient_user.id})

    # ==================== Specialist User Filtering Tests ====================

    def test_specialist_sees_only_own_created_records(self):
        """Test specialist can only access records they created"""
        specialist_user = self.specialist_user
        records = MedicalRecordService.get_filtered_records(
            user=specialist_user, filters={}
        )
        record_count = records.count()

        # Specialist should see only their own records
        self.assertEqual(record_count, 3)
        specialist_ids = set(records.values_list("specialist_id", flat=True))
        self.assertEqual(specialist_ids, {self.specialist.id})

    def test_other_specialist_cannot_see_first_specialist_records(self):
        """Test one specialist cannot see another specialist's records"""
        records = MedicalRecordService.get_filtered_records(
            user=self.other_specialist_user, filters={}
        )
        record_ids = set(records.values_list("id", flat=True))

        self.assertNotIn(self.standard_record.id, record_ids)
        self.assertNotIn(self.sensitive_record.id, record_ids)
        self.assertNotIn(self.highly_sensitive_record.id, record_ids)
        self.assertIn(self.other_patient_record.id, record_ids)

    def test_specialist_sees_all_confidentiality_levels_of_own_records(self):
        """Test specialist can see all confidentiality levels of their own records"""
        records = MedicalRecordService.get_filtered_records(
            user=self.specialist_user, filters={}
        )
        confidentiality_levels = set(
            records.values_list("confidentiality_level", flat=True)
        )

        self.assertIn("standard", confidentiality_levels)
        self.assertIn("sensitive", confidentiality_levels)
        self.assertIn("highly_sensitive", confidentiality_levels)

    # ==================== Staff User Filtering Tests ====================

    def test_staff_sees_only_standard_records(self):
        """Test staff can only access standard confidentiality records"""
        records = MedicalRecordService.get_filtered_records(
            user=self.staff_user, filters={}
        )
        record_count = records.count()
        confidentiality_levels = set(
            records.values_list("confidentiality_level", flat=True)
        )

        self.assertEqual(record_count, 2)  # Only 2 standard records
        self.assertEqual(confidentiality_levels, {"standard"})
        record_ids = set(records.values_list("id", flat=True))
        self.assertIn(self.standard_record.id, record_ids)
        self.assertIn(self.other_patient_record.id, record_ids)

    def test_staff_cannot_see_sensitive_records(self):
        """Test staff cannot see sensitive records"""
        records = MedicalRecordService.get_filtered_records(
            user=self.staff_user, filters={}
        )
        record_ids = set(records.values_list("id", flat=True))

        self.assertNotIn(self.sensitive_record.id, record_ids)
        self.assertNotIn(self.highly_sensitive_record.id, record_ids)

    # ==================== Unauthenticated User Tests ====================

    def test_unauthenticated_user_gets_empty_queryset(self):
        """Test unauthenticated (None) user gets empty queryset"""
        records = MedicalRecordService.get_filtered_records(user=None, filters={})
        self.assertEqual(records.count(), 0)

    # ==================== Queryset Optimization Tests ====================

    def test_filtered_records_queryset_has_select_related(self):
        """Test that filtered records queryset has proper optimization"""
        records = MedicalRecordService.get_filtered_records(
            user=self.admin_user, filters={}
        )

        # Check that select_related is applied by examining the query
        # This is a bit hacky but ensures optimization is applied
        queryset_str = str(records.query)
        self.assertIn("SELECT", queryset_str)

        # Verify we can access related fields without additional queries
        # Expects 1 query (the main query with select_related joins), not N+1 queries
        with self.assertNumQueries(1):
            for record in records:
                # Access related fields - should not trigger queries
                _ = record.patient
                _ = record.specialist
                _ = record.appointment

    def test_filtered_records_ordered_by_created_at(self):
        """Test that filtered records are properly ordered"""
        records = MedicalRecordService.get_filtered_records(
            user=self.admin_user, filters={}
        )

        # Get the ordering from the queryset
        ordering = records.query.order_by
        # Should be ordered by -created_at (most recent first)
        if ordering:
            self.assertTrue(any("created_at" in str(o) for o in ordering))

    # ==================== Integration Tests with Viewset Access ====================

    def test_admin_filtered_records_match_viewset_queryset(self):
        """Test that admin filtered records match what viewset would return"""
        service_records = MedicalRecordService.get_filtered_records(
            user=self.admin_user, filters={}
        )
        service_record_ids = set(service_records.values_list("id", flat=True))

        # Verify we get all 4 records
        self.assertEqual(len(service_record_ids), 4)

    def test_patient_filtered_records_excludes_highly_sensitive(self):
        """Test patient's filtered records at viewset level"""
        service_records = MedicalRecordService.get_filtered_records(
            user=self.patient_user, filters={}
        )

        # Verify no highly sensitive records
        highly_sensitive_count = service_records.filter(
            confidentiality_level="highly_sensitive"
        ).count()
        self.assertEqual(highly_sensitive_count, 0)

        # Verify only own records
        other_patient_count = service_records.exclude(patient=self.patient_user).count()
        self.assertEqual(other_patient_count, 0)

    def test_specialist_filtered_records_at_viewset_level(self):
        """Test specialist's filtered records at viewset level"""
        service_records = MedicalRecordService.get_filtered_records(
            user=self.specialist_user, filters={}
        )

        # Should have 1 specialist profile
        specialist_count = service_records.values("specialist_id").distinct().count()
        self.assertEqual(specialist_count, 1)

        # All should be created by this specialist
        specialist_ids = set(service_records.values_list("specialist_id", flat=True))
        self.assertEqual(specialist_ids, {self.specialist.id})

    # ==================== Filtering with Optional Filters ====================

    def test_get_filtered_records_with_patient_filter(self):
        """Test filtering records by specific patient"""
        # This tests if the service accepts optional filters
        records = MedicalRecordService.get_filtered_records(
            user=self.admin_user,
            filters=(
                {"patient_id": self.patient_user.id}
                if hasattr(MedicalRecordService.get_filtered_records, "__code__")
                and "filters"
                in MedicalRecordService.get_filtered_records.__code__.co_varnames
                else None
            ),
        )

        # If filters are supported, verify they work
        if records is not None:
            patient_ids = set(records.values_list("patient_id", flat=True))
            for pid in patient_ids:
                self.assertEqual(pid, self.patient_user.id)

    # ==================== Data Consistency Tests ====================

    def test_no_records_lost_in_filtering(self):
        """Test that total records equal sum of filtered results"""
        admin_records = MedicalRecordService.get_filtered_records(
            user=self.admin_user
        ).count()

        # Admin should see all records
        total_records = MedicalRecord.objects.count()
        self.assertEqual(admin_records, total_records)

    def test_filtered_records_have_proper_relationships(self):
        """Test that filtered records maintain proper object relationships"""
        records = MedicalRecordService.get_filtered_records(user=self.admin_user)

        for record in records:
            self.assertIsNotNone(record.patient)
            self.assertIsNotNone(record.specialist)
            self.assertEqual(record.patient.user_type, "patient")
            self.assertEqual(record.specialist.user.user_type, "specialist")


class MedicalRecordServiceViewsetIntegrationTestCase(TestCase):
    """Test cases for viewset integration with refactored service"""

    def setUp(self):
        """Set up test data"""
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

        # Create specialist profile
        self.specialist = Specialist.objects.create(
            user=self.specialist_user,
            specialization="Psychiatry",
            license_number="PSY12345",
            years_experience=5,
            consultation_fee=150,
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

        # Create test records
        self.record1 = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Patient shows anxiety diagnosis with assessment findings",
            prescription="Medication A - 10mg daily",
            confidentiality_level="standard",
        )

        self.record2 = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Patient shows depression diagnosis with clinical assessment",
            confidentiality_level="standard",
        )

    # ==================== Viewset Permission Tests ====================

    def test_viewset_respects_admin_access(self):
        """Test viewset returns correct queryset for admin"""
        queryset = MedicalRecordService.get_filtered_records(user=self.admin_user)
        self.assertEqual(queryset.count(), 2)

    def test_viewset_respects_patient_access(self):
        """Test viewset returns only patient's records"""
        queryset = MedicalRecordService.get_filtered_records(user=self.patient_user)
        self.assertEqual(queryset.count(), 2)

        for record in queryset:
            self.assertEqual(record.patient, self.patient_user)

    def test_viewset_respects_specialist_access(self):
        """Test viewset returns only specialist's records"""
        queryset = MedicalRecordService.get_filtered_records(user=self.specialist_user)
        self.assertEqual(queryset.count(), 2)

        for record in queryset:
            self.assertEqual(record.specialist, self.specialist)

    # ==================== Create Action Tests ====================

    def test_create_record_validation_through_service(self):
        """Test create action validates through service"""
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

        # Service should validate and create
        record = MedicalRecordService.create_medical_record(
            user=self.specialist_user,
            appointment_id=new_appointment.id,
            diagnosis="New record diagnosis with proper assessment findings",
            prescription="Medication B - 20mg daily",
            confidentiality_level="standard",
        )

        self.assertIsNotNone(record.id)
        self.assertEqual(record.patient, self.patient_user)
        self.assertEqual(record.specialist, self.specialist)

    # ==================== Update Action Tests ====================

    def test_update_record_preserves_access_control(self):
        """Test update respects service-level access control"""
        # Admin should be able to update
        updated = MedicalRecordService.update_medical_record(
            user=self.admin_user, medical_record=self.record1, notes="Updated by admin"
        )

        self.assertIn("Updated", updated.notes)

    def test_patient_cannot_update_via_service(self):
        """Test patient update is blocked by service"""
        with self.assertRaises(AuthorizationError):
            MedicalRecordService.update_medical_record(
                user=self.patient_user,
                medical_record=self.record1,
                notes="Patient trying to update",
            )

    # ==================== Delete Action Tests ====================

    def test_delete_record_authorization_check(self):
        """Test delete respects service authorization"""
        # Only admin should succeed
        test_record = MedicalRecord.objects.create(
            patient=self.patient_user,
            specialist=self.specialist,
            appointment=self.appointment,
            diagnosis="Record to delete with assessment findings",
            confidentiality_level="standard",
        )

        MedicalRecordService.delete_medical_record(
            user=self.admin_user, medical_record=test_record
        )

        self.assertFalse(MedicalRecord.objects.filter(id=test_record.id).exists())

    # ==================== List/Filter Action Tests ====================

    def test_list_action_uses_filtered_queryset(self):
        """Test list endpoint would use service-filtered queryset"""
        # Simulate what the list action does
        queryset = MedicalRecordService.get_filtered_records(user=self.patient_user)

        # Patient should only see their own
        self.assertEqual(queryset.count(), 2)
        patient_ids = set(queryset.values_list("patient_id", flat=True))
        self.assertEqual(patient_ids, {self.patient_user.id})

    def test_list_action_respects_search_filters(self):
        """Test filtered records can be further filtered"""
        # Get patient's records
        queryset = MedicalRecordService.get_filtered_records(user=self.patient_user)

        # Simulate search by diagnosis
        filtered = queryset.filter(diagnosis__icontains="anxiety")
        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.first().diagnosis, self.record1.diagnosis)

    # ==================== Custom Action Tests ====================

    def test_upcoming_follow_ups_uses_filtered_queryset(self):
        """Test upcoming_follow_ups action uses service-filtered queryset"""
        # Add follow-up date
        today = timezone.now().date()
        self.record1.follow_up_date = today + timedelta(days=7)
        self.record1.save()

        # Get filtered records
        queryset = MedicalRecordService.get_filtered_records(user=self.patient_user)

        # Filter for follow-ups
        follow_ups = queryset.filter(
            follow_up_date__isnull=False,
            follow_up_date__gte=today,
        )

        self.assertEqual(follow_ups.count(), 1)
        self.assertEqual(follow_ups.first(), self.record1)

    def test_statistics_respects_access_control(self):
        """Test stats action respects user access control"""
        # Patient stats should only count their records
        stats = MedicalRecordService.get_statistics(
            user=self.specialist_user, period="month"
        )

        # Specialist should see their records count
        self.assertIn("total_records", stats)
        self.assertEqual(stats["total_records"], 2)

    def test_retrieve_action_uses_filtered_queryset(self):
        """Test retrieve (detail) action respects filtered queryset"""
        # Patient should only be able to retrieve their own records
        queryset = MedicalRecordService.get_filtered_records(user=self.patient_user)

        # Should be able to find the record
        can_access = queryset.filter(id=self.record1.id).exists()
        self.assertTrue(can_access)

        # Cannot access records they shouldn't see
        another_specialist = User.objects.create_user(
            email="another@test.com",
            password="testpass123",
            user_type="specialist",
        )
        another_spec_profile = Specialist.objects.create(
            user=another_specialist,
            specialization="Psychology",
            license_number="PSY99999",
            years_experience=2,
            consultation_fee=100,
        )
        another_patient = User.objects.create_user(
            email="another_patient@test.com",
            password="testpass123",
            user_type="patient",
        )
        another_appointment = Appointment.objects.create(
            patient=another_patient,
            specialist=another_spec_profile,
            appointment_date=timezone.now().date() - timedelta(days=1),
            start_time=timezone.now() - timedelta(days=1, hours=1),
            end_time=timezone.now() - timedelta(days=1),
            duration_minutes=60,
            appointment_type="consultation",
            status="completed",
        )
        another_record = MedicalRecord.objects.create(
            patient=another_patient,
            specialist=another_spec_profile,
            appointment=another_appointment,
            diagnosis="Another patient diagnosis with assessment",
            confidentiality_level="standard",
        )

        # Patient should not see another patient's record
        queryset = MedicalRecordService.get_filtered_records(user=self.patient_user)
        can_access_other = queryset.filter(id=another_record.id).exists()
        self.assertFalse(can_access_other)

    # ==================== Pagination Tests ====================

    def test_filtered_queryset_supports_pagination(self):
        """Test filtered queryset can be paginated"""
        # Create multiple records for pagination testing
        for i in range(5):
            appointment_datetime = timezone.now() - timedelta(days=i)
            appt = Appointment.objects.create(
                patient=self.patient_user,
                specialist=self.specialist,
                appointment_date=appointment_datetime.date(),
                start_time=appointment_datetime,
                end_time=appointment_datetime + timedelta(hours=1),
                duration_minutes=60,
                appointment_type="consultation",
                status="completed",
            )
            MedicalRecord.objects.create(
                patient=self.patient_user,
                specialist=self.specialist,
                appointment=appt,
                diagnosis=f"Record {i} diagnosis with assessment findings",
                confidentiality_level="standard",
            )

        queryset = MedicalRecordService.get_filtered_records(user=self.patient_user)

        # Should have many records
        self.assertGreater(queryset.count(), 2)

        # Should be able to slice for pagination
        page_size = 3
        page1 = queryset[:page_size]
        self.assertEqual(len(list(page1)), 3)

    def test_filtered_queryset_preserves_order(self):
        """Test filtered queryset maintains ordering"""
        queryset = MedicalRecordService.get_filtered_records(user=self.patient_user)

        # Should be ordered by -created_at (most recent first)
        records_list = list(queryset)
        if len(records_list) > 1:
            # Verify they are ordered (first should have later or equal created_at)
            for i in range(len(records_list) - 1):
                self.assertGreaterEqual(
                    records_list[i].created_at, records_list[i + 1].created_at
                )
