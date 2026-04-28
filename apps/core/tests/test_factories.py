"""
Test script to verify all factories work correctly
Run with: python manage.py test apps.core.tests.test_factories
"""

from django.test import TestCase
from apps.core.management.db_data_factories import (
    UserFactory,
    PatientUserFactory,
    SpecialistUserFactory,
    AdminUserFactory,
    StaffUserFactory,
    SpecialistFactory,
    ServiceFactory,
    SpecialistServiceFactory,
    AvailabilityFactory,
    AppointmentFactory,
    MedicalRecordFactory,
    BillFactory,
    BillItemFactory,
    PaymentFactory,
    PaymentMethodFactory,
    InsuranceClaimFactory,
    RefundFactory,
    NotificationFactory,
)


class FactoriesTestCase(TestCase):
    """Test all model factories"""

    def test_user_factory(self):
        """Test UserFactory creates valid users"""
        user = UserFactory()
        self.assertIsNotNone(user.id)
        self.assertTrue(user.email)
        self.assertTrue(user.first_name)
        self.assertTrue(user.last_name)
        self.assertTrue(user.check_password("password123"))

    def test_patient_user_factory(self):
        """Test PatientUserFactory creates patients"""
        patient = PatientUserFactory()
        self.assertEqual(patient.user_type, "patient")
        self.assertTrue(patient.is_patient())

    def test_specialist_user_factory(self):
        """Test SpecialistUserFactory creates specialists"""
        specialist_user = SpecialistUserFactory()
        self.assertEqual(specialist_user.user_type, "specialist")
        self.assertTrue(specialist_user.is_specialist())

    def test_admin_user_factory(self):
        """Test AdminUserFactory creates admins"""
        admin = AdminUserFactory()
        self.assertEqual(admin.user_type, "admin")
        self.assertTrue(admin.is_admin())
        self.assertTrue(admin.is_staff)

    def test_staff_user_factory(self):
        """Test StaffUserFactory creates staff"""
        staff = StaffUserFactory()
        self.assertEqual(staff.user_type, "staff")
        self.assertTrue(staff.is_staff)

    def test_specialist_factory(self):
        """Test SpecialistFactory creates specialist profiles"""
        specialist = SpecialistFactory()
        self.assertIsNotNone(specialist.id)
        self.assertTrue(specialist.license_number)
        self.assertTrue(specialist.specialization)
        self.assertGreater(specialist.years_experience, 0)
        self.assertGreater(specialist.consultation_fee, 0)
        self.assertEqual(specialist.user.user_type, "specialist")

    def test_service_factory(self):
        """Test ServiceFactory creates services"""
        service = ServiceFactory()
        self.assertIsNotNone(service.id)
        self.assertTrue(service.name)
        self.assertTrue(service.category)
        self.assertGreater(service.duration_minutes, 0)
        self.assertGreater(service.base_price, 0)

    def test_specialist_service_factory(self):
        """Test SpecialistServiceFactory links specialists to services"""
        specialist_service = SpecialistServiceFactory()
        self.assertIsNotNone(specialist_service.id)
        self.assertIsNotNone(specialist_service.specialist)
        self.assertIsNotNone(specialist_service.service)

    def test_availability_factory(self):
        """Test AvailabilityFactory creates availability schedules"""
        availability = AvailabilityFactory()
        self.assertIsNotNone(availability.id)
        self.assertIsNotNone(availability.specialist)
        self.assertIsNotNone(availability.start_time)
        self.assertIsNotNone(availability.end_time)
        self.assertGreaterEqual(availability.day_of_week, 0)
        self.assertLessEqual(availability.day_of_week, 6)

    def test_appointment_factory(self):
        """Test AppointmentFactory creates appointments"""
        appointment = AppointmentFactory()
        self.assertIsNotNone(appointment.id)
        self.assertIsNotNone(appointment.patient)
        self.assertIsNotNone(appointment.specialist)
        self.assertIsNotNone(appointment.appointment_date)
        self.assertIsNotNone(appointment.start_time)
        self.assertIsNotNone(appointment.end_time)
        self.assertGreater(appointment.duration_minutes, 0)
        self.assertTrue(appointment.patient.is_patient())

    def test_medical_record_factory(self):
        """Test MedicalRecordFactory creates medical records"""
        record = MedicalRecordFactory()
        self.assertIsNotNone(record.id)
        self.assertIsNotNone(record.patient)
        self.assertIsNotNone(record.specialist)
        self.assertIsNotNone(record.appointment)
        self.assertTrue(record.diagnosis)
        self.assertEqual(record.patient, record.appointment.patient)
        self.assertEqual(record.specialist, record.appointment.specialist)

    def test_bill_factory(self):
        """Test BillFactory creates bills"""
        bill = BillFactory()
        self.assertIsNotNone(bill.id)
        self.assertTrue(bill.bill_number)
        self.assertIsNotNone(bill.appointment)
        self.assertIsNotNone(bill.patient)
        self.assertGreater(bill.total_amount, 0)
        self.assertGreaterEqual(bill.subtotal, 0)
        self.assertEqual(bill.patient, bill.appointment.patient)

    def test_bill_item_factory(self):
        """Test BillItemFactory creates bill items"""
        item = BillItemFactory()
        self.assertIsNotNone(item.id)
        self.assertIsNotNone(item.bill)
        self.assertTrue(item.description)
        self.assertGreater(item.unit_price, 0)
        self.assertGreater(item.quantity, 0)

    def test_payment_factory(self):
        """Test PaymentFactory creates payments"""
        payment = PaymentFactory()
        self.assertIsNotNone(payment.id)
        self.assertTrue(payment.payment_number)
        self.assertIsNotNone(payment.bill)
        self.assertIsNotNone(payment.patient)
        self.assertGreater(payment.amount, 0)
        self.assertTrue(payment.payment_method)

    def test_payment_method_factory(self):
        """Test PaymentMethodFactory creates payment methods"""
        method = PaymentMethodFactory()
        self.assertIsNotNone(method.id)
        self.assertIsNotNone(method.patient)
        self.assertTrue(method.stripe_payment_method_id)
        self.assertTrue(method.card_last4)
        self.assertTrue(method.patient.is_patient())

    def test_insurance_claim_factory(self):
        """Test InsuranceClaimFactory creates insurance claims"""
        claim = InsuranceClaimFactory()
        self.assertIsNotNone(claim.id)
        self.assertTrue(claim.claim_number)
        self.assertIsNotNone(claim.bill)
        self.assertIsNotNone(claim.patient)
        self.assertTrue(claim.insurance_company)
        self.assertTrue(claim.policy_number)
        self.assertGreater(claim.total_claimed_amount, 0)

    def test_refund_factory(self):
        """Test RefundFactory creates refunds"""
        refund = RefundFactory()
        self.assertIsNotNone(refund.id)
        self.assertTrue(refund.refund_number)
        self.assertIsNotNone(refund.payment)
        self.assertIsNotNone(refund.bill)
        self.assertGreater(refund.amount, 0)
        self.assertTrue(refund.reason)

    def test_notification_factory(self):
        """Test NotificationFactory creates notifications"""
        notification = NotificationFactory()
        self.assertIsNotNone(notification.id)
        self.assertIsNotNone(notification.user)
        self.assertTrue(notification.notification_type)
        self.assertTrue(notification.category)
        self.assertTrue(notification.title)
        self.assertTrue(notification.message)

    def test_batch_creation(self):
        """Test creating multiple instances in batch"""
        patients = PatientUserFactory.create_batch(10)
        self.assertEqual(len(patients), 10)
        for patient in patients:
            self.assertTrue(patient.is_patient())

        services = ServiceFactory.create_batch(5)
        self.assertEqual(len(services), 5)

    def test_related_objects_consistency(self):
        """Test that related objects are consistent"""
        # Create a complete flow: appointment -> medical record -> bill -> payment
        appointment = AppointmentFactory()

        # Medical record should use same patient and specialist
        record = MedicalRecordFactory(
            patient=appointment.patient,
            specialist=appointment.specialist,
            appointment=appointment,
        )

        self.assertEqual(record.patient, appointment.patient)
        self.assertEqual(record.specialist, appointment.specialist)
        self.assertEqual(record.appointment, appointment)

        # Bill should use same appointment and patient
        bill = BillFactory(appointment=appointment)
        self.assertEqual(bill.patient, appointment.patient)
        self.assertEqual(bill.appointment, appointment)

        # Payment should use same bill and patient
        payment = PaymentFactory(bill=bill)
        self.assertEqual(payment.bill, bill)
        self.assertEqual(payment.patient, bill.patient)

    def test_unique_constraints(self):
        """Test that unique constraints are respected"""
        user1 = UserFactory(email="test@example.com")

        # Creating another user with same email should use existing
        user2 = UserFactory(email="test@example.com")
        self.assertEqual(user1.id, user2.id)

    def test_factory_data_validity(self):
        """Test that factory-generated data is valid"""
        specialist = SpecialistFactory()

        # Check consultation fee is positive
        self.assertGreater(specialist.consultation_fee, 0)

        # Check years experience is valid
        self.assertGreaterEqual(specialist.years_experience, 1)
        self.assertLessEqual(specialist.years_experience, 30)

        # Check rating is within valid range
        self.assertGreaterEqual(specialist.rating, 0)
        self.assertLessEqual(specialist.rating, 5)

        # Test appointment duration is valid
        appointment = AppointmentFactory()
        valid_durations = [30, 45, 60, 90]
        self.assertIn(appointment.duration_minutes, valid_durations)

        # Test bill amounts are consistent
        bill = BillFactory()
        expected_total = bill.subtotal + bill.tax_amount - bill.discount_amount
        self.assertEqual(bill.total_amount, expected_total)
