import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncMonth
from django.db.models import QuerySet
from apps.core.exceptions.base_exceptions import (
    AuthorizationError,
    NotFoundError,
    BusinessRuleError,
)
from apps.billing.models import Bill, BillItem, Payment
from apps.appointments.models import Appointment
from apps.users.models import User

logger = logging.getLogger(__name__)


class BillingService:
    """Service layer for billing business logic"""

    # Minimum payment amount
    MIN_PAYMENT_AMOUNT = Decimal("0.5")

    # Default due date (14 days)
    DEFAULT_DUE_DAYS = 14

    # Tax rate (default)
    DEFAULT_TAX_RATE = Decimal("8.5")

    @staticmethod
    def get_bill_queryset(user: User) -> QuerySet[Bill]:
        """
        Get bill queryset with access control

        Args:
            user: Authenticated user

        Returns:
            Filtered QuerySet of bills
        """
        if user.is_anonymous:
            return Bill.objects.none()

        queryset = Bill.objects.select_related(
            "patient",
            "appointment",
            "appointment__specialist",
            "appointment__specialist__user",
        ).prefetch_related("items", "payments")

        if user.user_type == "patient":
            queryset = queryset.filter(patient=user)
        elif user.user_type == "specialist":
            if hasattr(user, "specialist_profile"):
                queryset = queryset.filter(
                    appointment__specialist=user.specialist_profile
                )
        # Admin and staff see all bills

        return queryset

    @staticmethod
    def calculate_bill_amounts(appointment: Appointment) -> Dict[str, Decimal]:
        """
        Calculate bill amounts for an appointment

        Args:
            appointment: Appointment instance

        Returns:
            Dictionary with subtotal, tax_amount, discount_amount, total_amount
        """
        try:
            # Get specialist consultation fee
            consultation_fee = appointment.specialist.consultation_fee

            # Calculate base amount
            subtotal = consultation_fee

            # Calculate tax
            tax_amount = (subtotal * BillingService.DEFAULT_TAX_RATE) / Decimal("100")

            # Calculate total
            total_amount = subtotal + tax_amount

            logger.info(
                f"Calculated bill amounts for appointment {appointment.id}: "
                f"subtotal={subtotal}, tax={tax_amount}, total={total_amount}"
            )

            return {
                "subtotal": subtotal,
                "tax_amount": tax_amount,
                "discount_amount": Decimal("0"),
                "total_amount": total_amount,
            }

        except AttributeError as e:
            logger.error(f"Error calculating bill amounts: {str(e)}")
            raise BusinessRuleError(
                detail="Cannot calculate bill amounts: specialist or fee information missing"
            )

    @staticmethod
    def validate_bill_creation(appointment: Appointment, user: User) -> None:
        """
        Validate if bill can be created

        Args:
            appointment: Appointment to bill
            user: User creating the bill

        Raises:
            BusinessRuleError: If validation fails
            AuthorizationError: If user lacks permissions
        """
        # Check if appointment is completed
        if appointment.status != "completed":
            raise BusinessRuleError(
                detail="Bills can only be created for completed appointments"
            )

        # Check if bill already exists
        if hasattr(appointment, "bill"):
            raise BusinessRuleError(detail="Bill already exists for this appointment")

        # Check permissions
        if user.user_type == "specialist":
            if not hasattr(user, "specialist_profile"):
                raise AuthorizationError(detail="Specialist profile not found")

            if appointment.specialist != user.specialist_profile:
                raise AuthorizationError(
                    detail="You can only create bills for your own appointments"
                )

        elif user.user_type not in ["admin", "staff"]:
            raise AuthorizationError(
                detail="Only admins, staff, or specialists can create bills"
            )

    @staticmethod
    def can_view_bill(user: User, bill: Bill) -> bool:
        """
        Check if user can view bill

        Args:
            user: User to check
            bill: Bill to view

        Returns:
            True if user can view the bill
        """
        if user.user_type == "admin":
            return True

        if user.user_type == "patient" and bill.patient == user:
            return True

        if user.user_type == "specialist":
            if (
                hasattr(user, "specialist_profile")
                and bill.appointment.specialist == user.specialist_profile
            ):
                return True

        if user.user_type == "staff":
            return True

        return False

    @staticmethod
    def can_update_bill(user: User, bill: Bill) -> bool:
        """
        Check if user can update bill

        Args:
            user: User to check
            bill: Bill to update

        Returns:
            True if user can update the bill
        """
        # Only admin and staff can update bills
        return user.user_type in ["admin", "staff"]

    @classmethod
    @transaction.atomic
    def create_bill_from_appointment(
        cls, appointment_id: int, created_by: User, **validated_data
    ) -> Bill:
        """
        Create a new bill from appointment

        Args:
            appointment_id: ID of appointment to bill
            created_by: User creating the bill
            **validated_data: Additional bill data

        Returns:
            Created Bill instance

        Raises:
            NotFoundError: If appointment not found
            BusinessRuleError: If validation fails
        """
        try:
            appointment = Appointment.objects.select_related(
                "patient", "specialist"
            ).get(id=appointment_id)
        except Appointment.DoesNotExist:
            raise NotFoundError(detail="Appointment not found")

        # Validate creation
        cls.validate_bill_creation(appointment, created_by)

        # Get calculated amounts
        amounts = cls.calculate_bill_amounts(appointment)

        # Set due date (default 14 days from now)
        due_date = validated_data.get("due_date")
        if not due_date:
            due_date = timezone.now().date() + timedelta(days=cls.DEFAULT_DUE_DAYS)

        # Create bill
        bill = Bill.objects.create(
            appointment=appointment,
            patient=appointment.patient,
            subtotal=amounts["subtotal"],
            tax_amount=amounts["tax_amount"],
            discount_amount=amounts["discount_amount"],
            total_amount=amounts["total_amount"],
            due_date=due_date,
            insurance_company=validated_data.get("insurance_company"),
            policy_number=validated_data.get("policy_number"),
            insurance_coverage=validated_data.get(
                "insurance_coverage", Decimal("0.00")
            ),
            notes=validated_data.get("notes", ""),
            terms_and_conditions=validated_data.get("terms_and_conditions", ""),
            created_by=created_by,
        )

        # Create bill item for consultation
        BillItem.objects.create(
            bill=bill,
            description=f"Consultation - {appointment.get_appointment_type_display()}",
            quantity=1,
            unit_price=appointment.specialist.consultation_fee,
            tax_rate=cls.DEFAULT_TAX_RATE,
            discount_rate=0,
            service=None,
        )

        logger.info(
            f"Bill created: {bill.bill_number} for appointment {appointment.id}, "
            f"total: ${bill.total_amount}"
        )

        return bill

    @classmethod
    @transaction.atomic
    def create_payment(
        cls,
        bill_id: int,
        amount: Decimal,
        payment_method: str,
        created_by: User,
        **kwargs,
    ) -> Payment:
        """
        Create a payment for a bill

        Args:
            bill_id: ID of bill to pay
            amount: Payment amount
            payment_method: Payment method
            created_by: User creating payment
            **kwargs: Additional payment data

        Returns:
            Created Payment instance

        Raises:
            NotFoundError: If bill not found
            BusinessRuleError: If validation fails
        """
        try:
            bill = Bill.objects.get(id=bill_id)
        except Bill.DoesNotExist:
            raise NotFoundError(detail="Bill not found")

        # Validate payment
        if bill.invoice_status in ["paid", "cancelled"]:
            raise BusinessRuleError(
                detail=f"Cannot make payment for bill with status: {bill.invoice_status}"
            )

        if amount > bill.balance_due:
            raise BusinessRuleError(
                detail=f"Payment amount (${amount}) exceeds balance due (${bill.balance_due})"
            )

        if amount < cls.MIN_PAYMENT_AMOUNT:
            raise BusinessRuleError(
                detail=f"Minimum payment amount is ${cls.MIN_PAYMENT_AMOUNT}"
            )

        # Validate bank reference for transfers
        if payment_method == "bank_transfer" and not kwargs.get("bank_reference"):
            raise BusinessRuleError(
                detail="Bank reference is required for bank transfers"
            )

        # Create payment record
        payment_data = {
            "bill": bill,
            "patient": bill.patient,
            "amount": amount,
            "payment_method": payment_method,
            "status": "pending",
            "created_by": created_by,
            "notes": kwargs.get("notes", ""),
            "admin_notes": kwargs.get("admin_notes", ""),
        }

        # Add payment method specific fields
        if payment_method == "bank_transfer":
            payment_data.update(
                {
                    "bank_reference": kwargs.get("bank_reference"),
                    "bank_name": kwargs.get("bank_name"),
                }
            )
        elif payment_method == "cash":
            # Auto-generate reference for cash payments
            payment_data["bank_reference"] = (
                f"CASH-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            )

        payment = Payment.objects.create(**payment_data)

        # For non-online payments, mark as completed immediately
        if payment_method != "online":
            payment.mark_as_completed()
            logger.info(
                f"Payment created and completed: {payment.payment_number} "
                f"for bill {bill.bill_number}, amount: ${amount}"
            )
        else:
            logger.info(
                f"Payment created (pending): {payment.payment_number} "
                f"for bill {bill.bill_number}, amount: ${amount}"
            )

        return payment

    @classmethod
    def get_billing_statistics(
        cls, period: str = "month", specialist_id: Optional[int] = None
    ) -> Dict:
        """
        Get billing statistics for the given period

        Args:
            period: Time period (today, week, month, year, all_time)
            specialist_id: Optional specialist ID to filter

        Returns:
            Dictionary with billing statistics
        """
        # Define date range
        now = timezone.now()
        start_date = None
        end_date = None

        if period == "today":
            start_date = now.date()
            end_date = now.date()
        elif period == "week":
            start_date = now.date() - timedelta(days=now.weekday())
            end_date = start_date + timedelta(days=6)
        elif period == "month":
            start_date = now.date().replace(day=1)
            if start_date.month == 12:
                end_date = start_date.replace(
                    year=start_date.year + 1, month=1, day=1
                ) - timedelta(days=1)
            else:
                end_date = start_date.replace(
                    month=start_date.month + 1, day=1
                ) - timedelta(days=1)
        elif period == "year":
            start_date = now.date().replace(month=1, day=1)
            end_date = now.date().replace(month=12, day=31)

        # Base queryset
        bills = Bill.objects.all()
        payments = Payment.objects.filter(status="completed")

        # Filter by specialist if provided
        if specialist_id:
            bills = bills.filter(appointment__specialist_id=specialist_id)
            payments = payments.filter(bill__appointment__specialist_id=specialist_id)

        # Filter by period if not all_time
        if period != "all_time" and start_date:
            bills = bills.filter(invoice_date__range=[start_date, end_date])
            payments = payments.filter(created_at__date__range=[start_date, end_date])

        # Calculate statistics using annotations for better performance
        bills_annotated = bills.annotate(
            paid_amount=Sum("payments__amount", filter=Q(payments__status="completed"))
        ).annotate(
            balance_due_calc=ExpressionWrapper(
                F("total_amount") - F("paid_amount"),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )

        total_bills = bills_annotated.count()
        total_revenue = bills_annotated.aggregate(total=Sum("total_amount"))[
            "total"
        ] or Decimal("0")
        total_collected = bills_annotated.aggregate(total=Sum("paid_amount"))[
            "total"
        ] or Decimal("0")
        total_outstanding = bills_annotated.aggregate(total=Sum("balance_due_calc"))[
            "total"
        ] or Decimal("0")

        # Payment method distribution
        payment_methods = (
            payments.values("payment_method")
            .annotate(count=Count("id"), total=Sum("amount"))
            .order_by("-total")
        )

        # Bill status distribution (calculated from payments)
        bill_status_summary = []
        status_counts = {
            "paid": 0,
            "partial": 0,
            "pending": 0,
            "overdue": 0,
        }

        for bill in bills_annotated:
            status = bill.payment_status
            if status in status_counts:
                status_counts[status] += 1

        for status, count in status_counts.items():
            if count > 0:
                bill_status_summary.append(
                    {
                        "payment_status": status,
                        "count": count,
                    }
                )

        # Average bill amount
        avg_bill_amount = bills_annotated.aggregate(avg=Avg("total_amount"))[
            "avg"
        ] or Decimal("0")

        # Overdue bills
        overdue_bills = bills_annotated.filter(
            due_date__lt=now.date(), invoice_status__in=["draft", "sent", "viewed"]
        )
        overdue_count = overdue_bills.count()
        overdue_amount = overdue_bills.aggregate(total=Sum("balance_due_calc"))[
            "total"
        ] or Decimal("0")

        # Monthly revenue trend (last 6 months)
        six_months_ago = now.date() - timedelta(days=180)
        monthly_trend = (
            bills.filter(invoice_date__gte=six_months_ago)
            .annotate(month=TruncMonth("invoice_date"))
            .values("month")
            .annotate(
                revenue=Sum("total_amount"),
                bills_count=Count("id"),
            )
            .order_by("month")
        )

        logger.info(
            f"Generated billing statistics for period '{period}', "
            f"specialist_id: {specialist_id}, total_bills: {total_bills}"
        )

        return {
            "period": period,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "summary": {
                "total_bills": total_bills,
                "total_revenue": float(total_revenue),
                "total_collected": float(total_collected),
                "total_outstanding": float(total_outstanding),
                "collection_rate": float(
                    (total_collected / total_revenue * 100) if total_revenue > 0 else 0
                ),
            },
            "payment_methods": list(payment_methods),
            "bill_statuses": bill_status_summary,
            "averages": {
                "avg_bill_amount": float(avg_bill_amount),
            },
            "overdue": {
                "count": overdue_count,
                "amount": float(overdue_amount),
            },
            "monthly_trend": list(monthly_trend),
        }

    @classmethod
    def get_user_billing_summary(cls, user: User) -> Dict:
        """
        Get billing summary for a user

        Args:
            user: User to get summary for

        Returns:
            Dictionary with billing summary
        """
        if user.user_type == "patient":
            bills = Bill.objects.filter(patient=user)
        elif user.user_type == "specialist":
            if hasattr(user, "specialist_profile"):
                bills = Bill.objects.filter(
                    appointment__specialist=user.specialist_profile
                )
            else:
                bills = Bill.objects.none()
        else:  # admin/staff
            bills = Bill.objects.all()

        # Annotate with payment information
        bills_annotated = bills.annotate(
            paid_amount=Sum("payments__amount", filter=Q(payments__status="completed"))
        ).annotate(
            balance_due_calc=ExpressionWrapper(
                F("total_amount") - F("paid_amount"),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )

        # Get overdue bills
        overdue = bills_annotated.filter(
            due_date__lt=timezone.now().date(),
            invoice_status__in=["draft", "sent", "viewed"],
        ).count()

        # Get pending bills (not fully paid)
        pending = bills_annotated.filter(
            invoice_status__in=["draft", "sent", "viewed"]
        ).count()

        # Get total balance due
        total_balance = bills_annotated.aggregate(total=Sum("balance_due_calc"))[
            "total"
        ] or Decimal("0")

        # Get recent bills
        recent_bills = bills_annotated.order_by("-invoice_date")[:10]

        logger.info(
            f"Generated billing summary for user {user.id}: "
            f"overdue={overdue}, pending={pending}, balance=${total_balance}"
        )

        return {
            "overdue_count": overdue,
            "pending_count": pending,
            "total_balance_due": float(total_balance),
            "recent_bills": recent_bills,
        }

    @staticmethod
    def get_overdue_bills(queryset: QuerySet[Bill]) -> List[Bill]:
        """
        Get overdue bills from queryset

        Args:
            queryset: Bill queryset to filter

        Returns:
            List of overdue bills sorted by days overdue
        """
        overdue_bills = queryset.filter(
            due_date__lt=timezone.now().date(),
            invoice_status__in=["draft", "sent", "viewed"],
        )

        # Sort by days overdue
        sorted_bills = sorted(
            overdue_bills,
            key=lambda b: (timezone.now().date() - b.due_date).days,
            reverse=True,
        )

        logger.info(f"Found {len(sorted_bills)} overdue bills")

        return sorted_bills

    @staticmethod
    def is_bill_ongoing(bill: Bill) -> bool:
        """
        Check if bill is still ongoing (not fully paid or cancelled)

        Args:
            bill: Bill to check

        Returns:
            True if bill is ongoing
        """
        return bill.payment_status not in ["paid", "cancelled"]

    @staticmethod
    @transaction.atomic
    def verify_bank_transfer_payment(
        payment_id: int, verified_by: User, notes: str = ""
    ) -> Payment:
        """
        Verify and complete a bank transfer payment

        Args:
            payment_id: ID of payment to verify
            verified_by: User verifying the payment
            notes: Additional notes

        Returns:
            Updated Payment instance

        Raises:
            NotFoundError: If payment not found
            BusinessRuleError: If validation fails
        """
        try:
            payment = Payment.objects.select_related("bill").get(id=payment_id)
        except Payment.DoesNotExist:
            raise NotFoundError(detail="Payment not found")

        if payment.payment_method != "bank_transfer":
            raise BusinessRuleError(
                detail="Only bank transfer payments can be verified"
            )

        if payment.status != "pending":
            raise BusinessRuleError(
                detail=f"Payment is already {payment.status}, cannot verify"
            )

        # Mark as completed
        payment.status = "completed"
        payment.processed_at = timezone.now()
        payment.admin_notes = f"Verified by {verified_by.email}: {notes}"
        payment.save()

        # Update bill status
        payment.bill.invoice_status = (
            "paid" if payment.bill.balance_due <= 0 else "sent"
        )
        payment.bill.save()

        logger.info(
            f"Bank transfer payment verified: {payment.payment_number}, "
            f"by {verified_by.email}"
        )

        return payment

    @classmethod
    @transaction.atomic
    def update_bill(cls, bill: Bill, user: User, **update_data) -> Bill:
        """
        Update a bill with validation

        Args:
            bill: Bill to update
            user: User updating the bill
            **update_data: Fields to update

        Returns:
            Updated Bill instance

        Raises:
            AuthorizationError: If user lacks permissions
        """
        if not cls.can_update_bill(user, bill):
            raise AuthorizationError(
                detail="You do not have permission to update this bill"
            )

        # Update allowed fields
        allowed_fields = [
            "insurance_company",
            "policy_number",
            "insurance_coverage",
            "notes",
            "due_date",
            "discount_amount",
        ]

        for field, value in update_data.items():
            if field in allowed_fields and value is not None:
                setattr(bill, field, value)

        bill.save()

        logger.info(f"Bill updated: {bill.bill_number} by user {user.id}")

        return bill

    @classmethod
    @transaction.atomic
    def mark_bill_as_paid(cls, bill: Bill, user: User, notes: str = "") -> Bill:
        """
        Mark a bill as paid

        Args:
            bill: Bill to mark as paid
            user: User marking bill as paid
            notes: Optional notes

        Returns:
            Updated Bill instance

        Raises:
            BusinessRuleError: If bill cannot be marked as paid
            AuthorizationError: If user lacks permissions
        """
        if not cls.can_update_bill(user, bill):
            raise AuthorizationError(
                detail="Only admin and staff can mark bills as paid"
            )

        if bill.invoice_status == "paid":
            raise BusinessRuleError(detail="Bill is already marked as paid")

        bill.invoice_status = "paid"
        bill.amount_paid = bill.total_amount
        bill.balance_due = Decimal("0")
        if notes:
            bill.notes = notes
        bill.save()

        logger.info(f"Bill marked as paid: {bill.bill_number} by user {user.id}")

        return bill

    @classmethod
    @transaction.atomic
    def cancel_bill(cls, bill: Bill, user: User, reason: str = "") -> Bill:
        """
        Cancel a bill

        Args:
            bill: Bill to cancel
            user: User canceling bill
            reason: Cancellation reason

        Returns:
            Cancelled Bill instance

        Raises:
            BusinessRuleError: If bill cannot be cancelled
            AuthorizationError: If user lacks permissions
        """
        if not cls.can_update_bill(user, bill):
            raise AuthorizationError(detail="Only admin and staff can cancel bills")

        if bill.invoice_status in ["paid", "cancelled"]:
            raise BusinessRuleError(
                detail=f"Cannot cancel bill with status: {bill.invoice_status}"
            )

        bill.invoice_status = "cancelled"
        bill.cancellation_date = timezone.now().date()
        if reason:
            bill.notes = reason
        bill.save()

        logger.info(
            f"Bill cancelled: {bill.bill_number} by user {user.id}, reason: {reason}"
        )

        return bill

    @staticmethod
    def send_payment_reminder(bill: Bill) -> Dict[str, Any]:
        """
        Send payment reminder for a bill

        Args:
            bill: Bill to send reminder for

        Returns:
            Dictionary with reminder sending status
        """
        try:
            from django.core.mail import EmailMessage
            from django.conf import settings

            subject = f"Payment Reminder: Invoice #{bill.bill_number}"

            # Generate email body
            body = f"""
            Dear {bill.patient.get_full_name()},

            This is a reminder that your invoice #{bill.bill_number} is due on {bill.due_date}.

            Invoice Details:
            - Invoice #: {bill.bill_number}
            - Issue Date: {bill.invoice_date}
            - Due Date: {bill.due_date}
            - Total Amount: ${bill.total_amount}
            - Amount Paid: ${bill.amount_paid}
            - Balance Due: ${bill.balance_due}

            Please pay your bill online at: {bill.get_payment_url()}

            If you have already made a payment, please disregard this reminder.

            Thank you,
            {settings.COMPANY_NAME}
            """

            # Create and send email
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[bill.patient.email],
            )

            # Uncomment to actually send email
            # email.send()

            logger.info(
                f"Payment reminder sent for bill {bill.bill_number} to {bill.patient.email}"
            )

            return {
                "status": "reminder_sent",
                "to": bill.patient.email,
                "subject": subject,
                "bill_number": bill.bill_number,
            }

        except Exception as e:
            logger.error(f"Error sending payment reminder: {str(e)}", exc_info=True)
            raise BusinessRuleError(detail="Failed to send payment reminder")
