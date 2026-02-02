from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta
from apps.appointments.models import Appointment
from apps.specialists.models import Specialist
from apps.users.models import User


class AppointmentModelTestCase(TestCase):
    """Test suite for Appointment model"""

    def setUp(self):
        """Set up test data"""
        # Create patient user
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
            user_type="patient",
        )

        # Create specialist user
        specialist_user = User.objects.create_user(
            email="specialist@test.com",
            password="testpass123",
            first_name="Dr. Jane",
            last_name="Smith",
            user_type="specialist",
        )

        # Create specialist
        self.specialist = Specialist.objects.create(
            user=specialist_user,
            license_number="LIC123456",
            specialization="psychologist",
            years_experience=5,
            consultation_fee=100.00,
        )

        # Define appointment times
        self.start_time = timezone.now() + timedelta(days=7, hours=2)
        self.end_time = self.start_time + timedelta(minutes=30)

    # =============================================
    # Tests for Model Creation
    # =============================================

    def test_create_appointment_success(self):
        """Test creating a valid appointment"""
        appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=30,
            status="scheduled",
            notes="First visit",
        )

        self.assertIsNotNone(appointment.id)
        self.assertEqual(appointment.patient, self.patient)
        self.assertEqual(appointment.specialist, self.specialist)
        self.assertEqual(appointment.appointment_type, "consultation")
        self.assertEqual(appointment.duration_minutes, 30)
        self.assertEqual(appointment.status, "scheduled")
        self.assertIsNotNone(appointment.created_at)
        self.assertIsNotNone(appointment.updated_at)

    def test_create_appointment_with_defaults(self):
        """Test creating appointment uses default values"""
        appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="therapy",
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=45,
        )

        # Check default values
        self.assertEqual(appointment.status, "scheduled")
        self.assertEqual(appointment.notes, "")
        self.assertEqual(appointment.symptoms, "")

    def test_create_appointment_with_meeting_link(self):
        """Test creating virtual appointment with meeting link"""
        appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=30,
            meeting_link="https://meet.example.com/xyz123",
        )

        self.assertEqual(appointment.meeting_link, "https://meet.example.com/xyz123")
        self.assertIsNone(appointment.room_number)

    def test_create_appointment_with_room_number(self):
        """Test creating physical appointment with room number"""
        appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="therapy",
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=60,
            room_number="201-A",
        )

        self.assertEqual(appointment.room_number, "201-A")
        self.assertIsNone(appointment.meeting_link)

    # =============================================
    # Tests for Model Validation
    # =============================================

    def test_appointment_type_choices(self):
        """Test appointment type must be from valid choices"""
        appointment = Appointment(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="invalid_type",  # Invalid choice
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=30,
        )

        with self.assertRaises(ValidationError):
            appointment.full_clean()

    def test_status_choices(self):
        """Test status must be from valid choices"""
        appointment = Appointment(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=30,
            status="invalid_status",  # Invalid choice
        )

        with self.assertRaises(ValidationError):
            appointment.full_clean()

    def test_duration_minutes_minimum_validator(self):
        """Test duration_minutes respects minimum validator"""
        appointment = Appointment(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=3,  # Less than minimum (5)
        )

        with self.assertRaises(ValidationError):
            appointment.full_clean()

    def test_required_fields(self):
        """Test that required fields cannot be null"""
        # Missing patient
        with self.assertRaises(IntegrityError):
            Appointment.objects.create(
                specialist=self.specialist,
                appointment_type="consultation",
                appointment_date=self.start_time,
                start_time=self.start_time,
                end_time=self.end_time,
                duration_minutes=30,
            )

    # =============================================
    # Tests for Model Methods
    # =============================================

    def test_str_representation(self):
        """Test string representation of appointment"""
        appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=30,
        )

        expected = f"John Doe with Dr. Jane Smith on {self.start_time}"
        self.assertEqual(str(appointment), expected)

    # =============================================
    # Tests for Model Relationships
    # =============================================

    def test_patient_relationship(self):
        """Test relationship between appointment and patient"""
        appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=30,
        )

        # Test forward relationship
        self.assertEqual(appointment.patient, self.patient)

        # Test reverse relationship
        self.assertIn(appointment, self.patient.appointments.all())

    def test_specialist_relationship(self):
        """Test relationship between appointment and specialist"""
        appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=30,
        )

        # Test forward relationship
        self.assertEqual(appointment.specialist, self.specialist)

        # Test reverse relationship
        self.assertIn(appointment, self.specialist.appointments.all())

    def test_cascade_delete_on_delete_setting(self):
        """Test model has CASCADE delete configured"""
        # Test that the ForeignKey fields have on_delete=CASCADE
        patient_field = Appointment._meta.get_field("patient")
        specialist_field = Appointment._meta.get_field("specialist")

        from django.db.models import CASCADE

        self.assertEqual(patient_field.remote_field.on_delete, CASCADE)
        self.assertEqual(specialist_field.remote_field.on_delete, CASCADE)

    # =============================================
    # Tests for Model Meta Options
    # =============================================

    def test_ordering(self):
        """Test default ordering of appointments"""
        # Create appointments with different dates
        appointment1 = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=30,
        )

        later_time = self.start_time + timedelta(days=1)
        appointment2 = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="therapy",
            appointment_date=later_time,
            start_time=later_time,
            end_time=later_time + timedelta(minutes=30),
            duration_minutes=30,
        )

        appointments = Appointment.objects.all()
        # Should be ordered by -appointment_date (descending)
        self.assertEqual(appointments[0], appointment2)
        self.assertEqual(appointments[1], appointment1)

    def test_verbose_names(self):
        """Test model verbose names"""
        self.assertEqual(Appointment._meta.verbose_name, "Appointment")
        self.assertEqual(Appointment._meta.verbose_name_plural, "Appointments")

    def test_db_table_name(self):
        """Test custom database table name"""
        self.assertEqual(Appointment._meta.db_table, "appointments")

    # =============================================
    # Tests for Timestamps
    # =============================================

    def test_created_at_auto_set(self):
        """Test created_at is automatically set"""
        before = timezone.now()
        appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=30,
        )
        after = timezone.now()

        self.assertIsNotNone(appointment.created_at)
        self.assertGreaterEqual(appointment.created_at, before)
        self.assertLessEqual(appointment.created_at, after)

    def test_updated_at_auto_updates(self):
        """Test updated_at is automatically updated on save"""
        appointment = Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=30,
        )

        original_updated_at = appointment.updated_at

        # Update appointment
        appointment.status = "confirmed"
        appointment.save()

        self.assertGreater(appointment.updated_at, original_updated_at)

    # =============================================
    # Tests for Querying
    # =============================================

    def test_filter_by_status(self):
        """Test filtering appointments by status"""
        Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=30,
            status="scheduled",
        )

        Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="therapy",
            appointment_date=self.start_time + timedelta(days=1),
            start_time=self.start_time + timedelta(days=1),
            end_time=self.end_time + timedelta(days=1),
            duration_minutes=45,
            status="confirmed",
        )

        scheduled = Appointment.objects.filter(status="scheduled")
        confirmed = Appointment.objects.filter(status="confirmed")

        self.assertEqual(scheduled.count(), 1)
        self.assertEqual(confirmed.count(), 1)

    def test_filter_by_patient(self):
        """Test filtering appointments by patient"""
        # Create another patient
        other_patient = User.objects.create_user(
            email="other@test.com",
            password="testpass123",
            first_name="Jane",
            last_name="Doe",
            user_type="patient",
        )

        # Create appointments for both patients
        Appointment.objects.create(
            patient=self.patient,
            specialist=self.specialist,
            appointment_type="consultation",
            appointment_date=self.start_time,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=30,
        )

        Appointment.objects.create(
            patient=other_patient,
            specialist=self.specialist,
            appointment_type="therapy",
            appointment_date=self.start_time + timedelta(days=1),
            start_time=self.start_time + timedelta(days=1),
            end_time=self.end_time + timedelta(days=1),
            duration_minutes=45,
        )

        patient_appointments = Appointment.objects.filter(patient=self.patient)
        self.assertEqual(patient_appointments.count(), 1)
        self.assertEqual(patient_appointments.first().patient, self.patient)
