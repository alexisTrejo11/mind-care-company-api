"""
Management command to populate the database with sample data using factories
"""

from django.core.management.base import BaseCommand
from django.db import transaction
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


class Command(BaseCommand):
    help = "Populate database with sample data for testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--users",
            type=int,
            default=50,
            help="Number of users to create (default: 50)",
        )
        parser.add_argument(
            "--specialists",
            type=int,
            default=20,
            help="Number of specialists to create (default: 20)",
        )
        parser.add_argument(
            "--services",
            type=int,
            default=30,
            help="Number of services to create (default: 30)",
        )
        parser.add_argument(
            "--appointments",
            type=int,
            default=100,
            help="Number of appointments to create (default: 100)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before populating",
        )

    def handle(self, *args, **options):
        num_users = options["users"]
        num_specialists = options["specialists"]
        num_services = options["services"]
        num_appointments = options["appointments"]
        clear_data = options["clear"]

        if clear_data:
            self.stdout.write(self.style.WARNING("Clearing existing data..."))
            self.clear_database()

        self.stdout.write(self.style.SUCCESS("Starting database population..."))

        try:
            with transaction.atomic():
                # Create admin and staff users
                self.stdout.write("Creating admin and staff users...")
                admin_user = AdminUserFactory(
                    email="admin@mindcarehub.com", first_name="Admin", last_name="User"
                )
                staff_users = StaffUserFactory.create_batch(3)
                self.stdout.write(
                    self.style.SUCCESS(f"Created 1 admin and 3 staff users")
                )

                # Create patient users
                self.stdout.write(f"Creating {num_users} patient users...")
                patients = PatientUserFactory.create_batch(num_users)
                self.stdout.write(self.style.SUCCESS(f"Created {num_users} patients"))

                # Create services
                self.stdout.write(f"Creating {num_services} services...")
                services = ServiceFactory.create_batch(num_services)
                self.stdout.write(
                    self.style.SUCCESS(f"Created {num_services} services")
                )

                # Create specialists
                self.stdout.write(f"Creating {num_specialists} specialists...")
                specialists = SpecialistFactory.create_batch(num_specialists)
                self.stdout.write(
                    self.style.SUCCESS(f"Created {num_specialists} specialists")
                )

                # Link specialists to services
                self.stdout.write("Linking specialists to services...")
                specialist_services_count = 0
                for specialist in specialists:
                    # Each specialist offers 3-6 random services
                    import random

                    num_services_per_specialist = random.randint(3, 6)
                    selected_services = random.sample(
                        services, min(num_services_per_specialist, len(services))
                    )
                    for service in selected_services:
                        SpecialistServiceFactory(specialist=specialist, service=service)
                        specialist_services_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created {specialist_services_count} specialist-service links"
                    )
                )

                # Create availability schedules for specialists
                self.stdout.write("Creating availability schedules...")
                availability_count = 0
                for specialist in specialists:
                    # Create availability for weekdays (Monday to Friday)
                    for day in range(1, 6):
                        AvailabilityFactory(specialist=specialist, day_of_week=day)
                        availability_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created {availability_count} availability schedules"
                    )
                )

                # Create appointments
                self.stdout.write(f"Creating {num_appointments} appointments...")
                appointments = []
                for _ in range(num_appointments):
                    import random

                    patient = random.choice(patients)
                    specialist = random.choice(specialists)
                    appointment = AppointmentFactory(
                        patient=patient, specialist=specialist
                    )
                    appointments.append(appointment)
                self.stdout.write(
                    self.style.SUCCESS(f"Created {num_appointments} appointments")
                )

                # Create medical records for completed appointments
                self.stdout.write("Creating medical records...")
                import random

                completed_appointments = random.sample(
                    appointments, min(num_appointments // 3, len(appointments))
                )
                medical_records = []
                for appointment in completed_appointments:
                    appointment.status = "completed"
                    appointment.save()
                    medical_record = MedicalRecordFactory(
                        patient=appointment.patient,
                        specialist=appointment.specialist,
                        appointment=appointment,
                    )
                    medical_records.append(medical_record)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created {len(medical_records)} medical records"
                    )
                )

                # Create bills for completed appointments
                self.stdout.write("Creating bills...")
                bills = []
                for appointment in completed_appointments:
                    bill = BillFactory(
                        appointment=appointment,
                        patient=appointment.patient,
                        created_by=random.choice(staff_users),
                    )
                    bills.append(bill)

                    # Add 1-3 bill items per bill
                    num_items = random.randint(1, 3)
                    for _ in range(num_items):
                        BillItemFactory(bill=bill, service=random.choice(services))
                self.stdout.write(
                    self.style.SUCCESS(f"Created {len(bills)} bills with items")
                )

                # Create payments for some bills
                self.stdout.write("Creating payments...")
                paid_bills = random.sample(bills, min(len(bills) // 2, len(bills)))
                payments = []
                for bill in paid_bills:
                    payment = PaymentFactory(
                        bill=bill,
                        patient=bill.patient,
                        amount=bill.total_amount,
                        status="completed",
                        created_by=random.choice(staff_users),
                    )
                    payments.append(payment)

                    # Mark bill as paid
                    bill.amount_paid = payment.amount
                    bill.payment_status = "paid"
                    bill.invoice_status = "paid"
                    bill.save()
                self.stdout.write(
                    self.style.SUCCESS(f"Created {len(payments)} payments")
                )

                # Create payment methods for some patients
                self.stdout.write("Creating payment methods...")
                payment_methods = []
                for patient in random.sample(patients, min(30, len(patients))):
                    payment_method = PaymentMethodFactory(patient=patient)
                    payment_methods.append(payment_method)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created {len(payment_methods)} payment methods"
                    )
                )

                # Create insurance claims for some bills
                self.stdout.write("Creating insurance claims...")
                insurance_bills = random.sample(bills, min(len(bills) // 4, len(bills)))
                insurance_claims = []
                for bill in insurance_bills:
                    claim = InsuranceClaimFactory(
                        bill=bill,
                        patient=bill.patient,
                        created_by=random.choice(staff_users),
                    )
                    insurance_claims.append(claim)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created {len(insurance_claims)} insurance claims"
                    )
                )

                # Create refunds for some payments
                self.stdout.write("Creating refunds...")
                refundable_payments = random.sample(
                    payments, min(len(payments) // 10, len(payments))
                )
                refunds = []
                for payment in refundable_payments:
                    refund = RefundFactory(
                        payment=payment,
                        bill=payment.bill,
                        created_by=random.choice(staff_users),
                    )
                    refunds.append(refund)
                self.stdout.write(self.style.SUCCESS(f"Created {len(refunds)} refunds"))

                # Create notifications for users
                self.stdout.write("Creating notifications...")
                notifications_count = 0
                all_users = (
                    patients
                    + [specialist.user for specialist in specialists]
                    + staff_users
                    + [admin_user]
                )
                for user in random.sample(all_users, min(100, len(all_users))):
                    # Create 1-5 notifications per selected user
                    num_notifications = random.randint(1, 5)
                    for _ in range(num_notifications):
                        NotificationFactory(user=user)
                        notifications_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Created {notifications_count} notifications")
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        "\n=== Database population completed successfully! ==="
                    )
                )
                self.stdout.write(self.style.SUCCESS(f"Summary:"))
                self.stdout.write(
                    f"  - Users: {num_users} patients, {num_specialists} specialists, 3 staff, 1 admin"
                )
                self.stdout.write(f"  - Services: {num_services}")
                self.stdout.write(f"  - Appointments: {num_appointments}")
                self.stdout.write(f"  - Medical Records: {len(medical_records)}")
                self.stdout.write(f"  - Bills: {len(bills)}")
                self.stdout.write(f"  - Payments: {len(payments)}")
                self.stdout.write(f"  - Insurance Claims: {len(insurance_claims)}")
                self.stdout.write(f"  - Refunds: {len(refunds)}")
                self.stdout.write(f"  - Notifications: {notifications_count}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error populating database: {str(e)}"))
            raise

    def clear_database(self):
        """Clear all data from the database"""
        from apps.users.models import User
        from apps.specialists.models import (
            Specialist,
            Service,
            SpecialistService,
            Availability,
        )
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
        from apps.notification.models import Notification

        # Delete in reverse order of dependencies
        Notification.objects.all().delete()
        Refund.objects.all().delete()
        InsuranceClaim.objects.all().delete()
        PaymentMethod.objects.all().delete()
        Payment.objects.all().delete()
        BillItem.objects.all().delete()
        Bill.objects.all().delete()
        MedicalRecord.objects.all().delete()
        Appointment.objects.all().delete()
        Availability.objects.all().delete()
        SpecialistService.objects.all().delete()
        Service.objects.all().delete()
        Specialist.objects.all().delete()
        User.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("Database cleared successfully"))
