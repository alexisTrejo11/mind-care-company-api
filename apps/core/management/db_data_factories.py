import factory
from factory.django import DjangoModelFactory
from factory import fuzzy
from django.utils import timezone
from datetime import timedelta, datetime, time
from decimal import Decimal
import random

from apps.appointments.models import Appointment
from apps.medical.models import MedicalRecord
from apps.billing.models import (
    Bill,
    BillItem,
    Payment,
    PaymentMethod,
    InsuranceClaim,
    Refund,
)
from apps.users.models import User
from apps.specialists.models import Specialist, Service, SpecialistService, Availability
from apps.notification.models import Notification


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    phone = factory.Faker("phone_number")
    date_of_birth = factory.Faker("date_of_birth", minimum_age=18, maximum_age=80)
    user_type = "patient"
    is_active = True
    is_staff = False
    password = factory.PostGenerationMethodCall("set_password", "password123")

    @factory.post_generation
    def set_password(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            obj.set_password(extracted)
        else:
            obj.set_password("password123")


class PatientUserFactory(UserFactory):
    """Factory for patient users"""

    user_type = "patient"


class SpecialistUserFactory(UserFactory):
    """Factory for specialist users"""

    user_type = "specialist"


class AdminUserFactory(UserFactory):
    """Factory for admin users"""

    user_type = "admin"
    is_staff = True


class StaffUserFactory(UserFactory):
    """Factory for staff users"""

    user_type = "staff"
    is_staff = True


class SpecialistFactory(DjangoModelFactory):
    class Meta:
        model = Specialist
        django_get_or_create = ("user",)

    user = factory.SubFactory(SpecialistUserFactory)
    license_number = factory.Sequence(lambda n: f"LIC-{n:06d}")
    specialization = factory.Faker(
        "random_element",
        elements=[choice[0] for choice in Specialist.SPECIALIZATION_CHOICES],
    )
    qualifications = factory.Faker("text", max_nb_chars=200)
    years_experience = factory.Faker("random_int", min=1, max=30)
    consultation_fee = factory.Faker(
        "pydecimal",
        left_digits=3,
        right_digits=2,
        positive=True,
        min_value=50,
        max_value=500,
    )
    is_accepting_new_patients = True
    is_active = True
    max_daily_appointments = factory.Faker("random_int", min=10, max=30)
    bio = factory.Faker("text", max_nb_chars=500)
    rating = factory.Faker(
        "pydecimal",
        left_digits=1,
        right_digits=2,
        positive=True,
        min_value=3,
        max_value=5,
    )


class ServiceFactory(DjangoModelFactory):
    class Meta:
        model = Service
        django_get_or_create = ("name", "category")

    name = factory.Sequence(lambda n: f"Service {n}")
    description = factory.Faker("text", max_nb_chars=300)
    category = factory.Faker(
        "random_element", elements=[choice[0] for choice in Service.CATEGORY_CHOICES]
    )
    duration_minutes = factory.Faker(
        "random_element", elements=[15, 30, 45, 60, 90, 120]
    )
    base_price = factory.Faker(
        "pydecimal",
        left_digits=3,
        right_digits=2,
        positive=True,
        min_value=30,
        max_value=300,
    )
    is_active = True


class SpecialistServiceFactory(DjangoModelFactory):
    class Meta:
        model = SpecialistService
        django_get_or_create = ("specialist", "service")

    specialist = factory.SubFactory(SpecialistFactory)
    service = factory.SubFactory(ServiceFactory)
    price_override = factory.Maybe(
        factory.Faker("boolean", chance_of_getting_true=30),
        yes_declaration=factory.Faker(
            "pydecimal",
            left_digits=3,
            right_digits=2,
            positive=True,
            min_value=40,
            max_value=350,
        ),
        no_declaration=None,
    )
    is_available = True


class AvailabilityFactory(DjangoModelFactory):
    class Meta:
        model = Availability

    specialist = factory.SubFactory(SpecialistFactory)
    day_of_week = factory.Faker("random_int", min=0, max=6)
    start_time = factory.LazyFunction(lambda: time(9, 0))  # 9:00 AM
    end_time = factory.LazyFunction(lambda: time(17, 0))  # 5:00 PM
    is_recurring = True
    valid_from = factory.LazyFunction(lambda: timezone.now().date())
    valid_until = None


class AppointmentFactory(DjangoModelFactory):
    class Meta:
        model = Appointment

    patient = factory.SubFactory(PatientUserFactory)
    specialist = factory.SubFactory(SpecialistFactory)
    appointment_type = factory.Faker(
        "random_element",
        elements=[choice[0] for choice in Appointment.APPOINTMENT_TYPE_CHOICES],
    )
    appointment_date = factory.LazyFunction(
        lambda: timezone.make_aware(
            datetime.combine(
                timezone.now().date() + timedelta(days=random.randint(1, 30)),
                time(random.randint(9, 16), 0),
            )
        )
    )
    start_time = factory.LazyAttribute(lambda obj: obj.appointment_date)
    end_time = factory.LazyAttribute(
        lambda obj: obj.start_time + timedelta(minutes=obj.duration_minutes)
    )
    duration_minutes = factory.Faker("random_element", elements=[30, 45, 60, 90])
    status = "scheduled"
    notes = factory.Faker("text", max_nb_chars=200)
    symptoms = factory.Faker("text", max_nb_chars=150)
    meeting_link = factory.Maybe(
        factory.Faker("boolean", chance_of_getting_true=40),
        yes_declaration=factory.Faker("url"),
        no_declaration=None,
    )
    room_number = factory.Maybe(
        factory.Faker("boolean", chance_of_getting_true=40),
        yes_declaration=factory.Faker(
            "random_element", elements=["101", "102", "201", "202", "301"]
        ),
        no_declaration=None,
    )


class MedicalRecordFactory(DjangoModelFactory):
    class Meta:
        model = MedicalRecord

    patient = factory.SubFactory(PatientUserFactory)
    specialist = factory.SubFactory(SpecialistFactory)
    appointment = factory.SubFactory(
        AppointmentFactory,
        patient=factory.SelfAttribute("..patient"),
        specialist=factory.SelfAttribute("..specialist"),
    )
    diagnosis = factory.Faker("text", max_nb_chars=300)
    prescription = factory.Faker("text", max_nb_chars=200)
    notes = factory.Faker("text", max_nb_chars=400)
    recommendations = factory.Faker("text", max_nb_chars=200)
    follow_up_date = factory.Maybe(
        factory.Faker("boolean", chance_of_getting_true=50),
        yes_declaration=factory.LazyFunction(
            lambda: timezone.now().date() + timedelta(days=random.randint(7, 90))
        ),
        no_declaration=None,
    )
    confidentiality_level = factory.Faker(
        "random_element",
        elements=[choice[0] for choice in MedicalRecord.CONFIDENTIALITY_CHOICES],
    )


class BillFactory(DjangoModelFactory):
    class Meta:
        model = Bill

    appointment = factory.SubFactory(AppointmentFactory)
    patient = factory.LazyAttribute(lambda obj: obj.appointment.patient)
    subtotal = factory.Faker(
        "pydecimal",
        left_digits=3,
        right_digits=2,
        positive=True,
        min_value=100,
        max_value=1000,
    )
    tax_amount = factory.LazyAttribute(
        lambda obj: (obj.subtotal * Decimal("0.08")).quantize(Decimal("0.01"))
    )
    discount_amount = Decimal("0.00")
    total_amount = factory.LazyAttribute(
        lambda obj: obj.subtotal + obj.tax_amount - obj.discount_amount
    )
    amount_paid = Decimal("0.00")
    balance_due = factory.LazyAttribute(lambda obj: obj.total_amount)
    invoice_status = "draft"
    payment_status = "pending"
    payment_method = None
    due_date = factory.LazyFunction(lambda: timezone.now().date() + timedelta(days=30))
    notes = factory.Faker("text", max_nb_chars=100)
    terms_and_conditions = factory.Faker("text", max_nb_chars=200)
    created_by = factory.SubFactory(StaffUserFactory)


class BillItemFactory(DjangoModelFactory):
    class Meta:
        model = BillItem

    bill = factory.SubFactory(BillFactory)
    description = factory.Faker("sentence", nb_words=5)
    quantity = Decimal("1.00")
    unit_price = factory.Faker(
        "pydecimal",
        left_digits=3,
        right_digits=2,
        positive=True,
        min_value=50,
        max_value=500,
    )
    tax_rate = Decimal("8.00")
    discount_rate = Decimal("0.00")
    service = factory.SubFactory(ServiceFactory)


class PaymentFactory(DjangoModelFactory):
    class Meta:
        model = Payment

    bill = factory.SubFactory(BillFactory)
    patient = factory.LazyAttribute(lambda obj: obj.bill.patient)
    amount = factory.LazyAttribute(lambda obj: obj.bill.total_amount)
    payment_method = factory.Faker(
        "random_element",
        elements=[choice[0] for choice in Payment.PAYMENT_METHOD_CHOICES],
    )
    currency = "USD"
    status = "pending"
    notes = factory.Faker("text", max_nb_chars=100)
    created_by = factory.SubFactory(StaffUserFactory)


class PaymentMethodFactory(DjangoModelFactory):
    class Meta:
        model = PaymentMethod

    patient = factory.SubFactory(PatientUserFactory)
    method_type = "card"
    is_default = False
    stripe_payment_method_id = factory.Sequence(lambda n: f"pm_test_{n}")
    stripe_customer_id = factory.Sequence(lambda n: f"cus_test_{n}")
    card_brand = factory.Faker(
        "random_element", elements=["Visa", "MasterCard", "Amex"]
    )
    card_last4 = factory.Faker("numerify", text="####")
    card_exp_month = factory.Faker("random_int", min=1, max=12)
    card_exp_year = factory.Faker("random_int", min=2024, max=2030)
    is_active = True


class InsuranceClaimFactory(DjangoModelFactory):
    class Meta:
        model = InsuranceClaim

    claim_number = factory.Sequence(lambda n: f"CLM-{n:08d}")
    bill = factory.SubFactory(BillFactory)
    patient = factory.LazyAttribute(lambda obj: obj.bill.patient)
    insurance_company = factory.Faker("company")
    policy_number = factory.Sequence(lambda n: f"POL-{n:08d}")
    group_number = factory.Sequence(lambda n: f"GRP-{n:06d}")
    subscriber_name = factory.Faker("name")
    subscriber_relationship = factory.Faker(
        "random_element", elements=["self", "spouse", "child", "parent"]
    )
    diagnosis_codes = factory.LazyFunction(
        lambda: [f"ICD-{random.randint(100, 999)}" for _ in range(random.randint(1, 3))]
    )
    procedure_codes = factory.LazyFunction(
        lambda: [
            f"CPT-{random.randint(10000, 99999)}" for _ in range(random.randint(1, 2))
        ]
    )
    total_claimed_amount = factory.LazyAttribute(lambda obj: obj.bill.total_amount)
    insurance_responsibility = factory.LazyAttribute(
        lambda obj: (obj.total_claimed_amount * Decimal("0.80")).quantize(
            Decimal("0.01")
        )
    )
    patient_responsibility = factory.LazyAttribute(
        lambda obj: obj.total_claimed_amount - obj.insurance_responsibility
    )
    denied_amount = Decimal("0.00")
    status = "draft"
    date_of_service = factory.LazyAttribute(lambda obj: obj.bill.invoice_date)
    notes = factory.Faker("text", max_nb_chars=200)
    created_by = factory.SubFactory(StaffUserFactory)


class RefundFactory(DjangoModelFactory):
    class Meta:
        model = Refund

    payment = factory.SubFactory(PaymentFactory)
    bill = factory.LazyAttribute(lambda obj: obj.payment.bill)
    amount = factory.LazyAttribute(lambda obj: obj.payment.amount)
    reason = factory.Faker(
        "random_element",
        elements=[choice[0] for choice in Refund.REFUND_REASON_CHOICES],
    )
    reason_details = factory.Faker("text", max_nb_chars=200)
    status = "requested"
    created_by = factory.SubFactory(StaffUserFactory)


class NotificationFactory(DjangoModelFactory):
    class Meta:
        model = Notification

    user = factory.SubFactory(UserFactory)
    notification_type = factory.Faker(
        "random_element", elements=[choice[0] for choice in Notification.TYPE_CHOICES]
    )
    category = factory.Faker(
        "random_element",
        elements=[choice[0] for choice in Notification.CATEGORY_CHOICES],
    )
    priority = factory.Faker(
        "random_element",
        elements=[choice[0] for choice in Notification.PRIORITY_CHOICES],
    )
    status = "pending"
    title = factory.Faker("sentence", nb_words=6)
    message = factory.Faker("text", max_nb_chars=200)
    metadata = factory.LazyFunction(dict)
    send_email = True
    send_sms = False
    send_push = False
    email_sent = False
    sms_sent = False
    push_sent = False
    retry_count = 0
    max_retries = 3
    is_read = False
