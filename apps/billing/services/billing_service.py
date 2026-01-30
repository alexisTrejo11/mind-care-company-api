import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from django.core.exceptions import ValidationError as DjangoValidationError

from core.exceptions.base_exceptions import (
    ValidationError,
    NotFoundError,
    BusinessRuleError,
    PaymentError,
)

from ..models import Bill, BillItem, Payment, Refund, InsuranceClaim
from apps.appointments.models import Appointment
from apps.specialists.models import Specialist, SpecialistService
from apps.users.models import User

logger = logging.getLogger(__name__)


class BillingService:
    """Main billing service with business logic"""

    @staticmethod
    @transaction.atomic
    def create_bill_from_appointment(
        appointment_id: int, created_by: User, due_date_days: int = 30, **kwargs
    ) -> Bill:
        """
        Create a bill from a completed appointment

        Args:
            appointment_id: Appointment ID
            created_by: User creating the bill
            due_date_days: Days until due date (default 30)
            **kwargs: Additional bill fields

        Returns:
            Bill object
        """
        try:
            # Get appointment with related data
            appointment = Appointment.objects.select_related(
                "patient", "specialist", "specialist__user"
            ).get(id=appointment_id)

            # Validate appointment
            if appointment.status != "completed":
                raise BusinessRuleError(
                    detail="Bills can only be created for completed appointments",
                    code="appointment_not_completed",
                )

            # Check if bill already exists
            if hasattr(appointment, "bill"):
                raise BusinessRuleError(
                    detail="Bill already exists for this appointment",
                    code="duplicate_bill",
                )

            # Calculate bill amounts
            amounts = BillingService._calculate_appointment_amounts(appointment)

            # Set due date
            due_date = timezone.now().date() + timedelta(days=due_date_days)

            # Create bill
            bill = Bill.objects.create(
                appointment=appointment,
                patient=appointment.patient,
                subtotal=amounts["subtotal"],
                tax_amount=amounts["tax_amount"],
                discount_amount=amounts.get("discount", Decimal("0.00")),
                total_amount=amounts["total"],
                amount_paid=Decimal("0.00"),
                balance_due=amounts["total"],
                due_date=due_date,
                created_by=created_by,
                **kwargs,
            )

            # Create bill items
            BillingService._create_bill_items(bill, appointment, amounts)

            # Handle insurance if applicable
            if kwargs.get("insurance_company"):
                BillingService._create_insurance_claim(bill, kwargs)

            logger.info(
                f"Bill created: {bill.bill_number} - "
                f"Appointment: {appointment_id}, "
                f"Total: ${bill.total_amount}"
            )

            return bill

        except Appointment.DoesNotExist:
            raise NotFoundError(detail="Appointment not found")
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e))
        except Exception as e:
            logger.error(f"Error creating bill: {str(e)}", exc_info=True)
            raise BusinessRuleError(detail="Failed to create bill")

    @staticmethod
    def _calculate_appointment_amounts(appointment: Appointment) -> Dict[str, Decimal]:
        """Calculate bill amounts for an appointment"""
        # Base consultation fee
        base_fee = appointment.specialist.consultation_fee

        # Adjust for appointment type
        fee_multiplier = {
            "consultation": Decimal("1.0"),
            "therapy": Decimal("1.5"),
            "follow_up": Decimal("0.75"),
            "emergency": Decimal("2.0"),
        }

        multiplier = fee_multiplier.get(appointment.appointment_type, Decimal("1.0"))
        subtotal = base_fee * multiplier

        # Add service fees if applicable
        # This would need integration with services

        # Apply tax (example: 8.25%)
        tax_rate = Decimal("8.25")
        tax_amount = (subtotal * tax_rate) / Decimal("100")

        # Total
        total = subtotal + tax_amount

        return {
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "tax_rate": tax_rate,
            "total": total,
        }

    @staticmethod
    def _create_bill_items(
        bill: Bill, appointment: Appointment, amounts: Dict[str, Decimal]
    ) -> List[BillItem]:
        """Create bill items for an appointment"""
        items = []

        # Main consultation item
        consultation_item = BillItem.objects.create(
            bill=bill,
            description=f"{appointment.specialist.specialization} Consultation",
            quantity=Decimal("1.0"),
            unit_price=amounts["subtotal"],
            tax_rate=amounts["tax_rate"],
            service=None,  # Could link to a service
        )
        items.append(consultation_item)

        # Additional services could be added here

        return items

    @staticmethod
    def _create_insurance_claim(
        bill: Bill, insurance_data: Dict[str, Any]
    ) -> InsuranceClaim:
        """Create insurance claim for bill"""
        # Generate claim number
        from datetime import datetime

        claim_number = f'CLM-{datetime.now().strftime("%Y%m")}-{bill.id:04d}'

        claim = InsuranceClaim.objects.create(
            claim_number=claim_number,
            bill=bill,
            patient=bill.patient,
            insurance_company=insurance_data.get("insurance_company"),
            policy_number=insurance_data.get("policy_number"),
            subscriber_name=bill.patient.get_full_name(),
            subscriber_relationship="self",
            total_claimed_amount=bill.total_amount,
            date_of_service=bill.appointment.appointment_date,
            status="draft",
            created_by=bill.created_by,
        )

        return claim

    @staticmethod
    @transaction.atomic
    def create_payment(
        bill_id: int,
        amount: Decimal,
        payment_method: str,
        patient: Optional[User] = None,
        created_by: Optional[User] = None,
        **kwargs,
    ) -> Payment:
        """
        Create a payment for a bill

        Args:
            bill_id: Bill ID
            amount: Payment amount
            payment_method: Payment method
            patient: Patient making payment
            created_by: User creating payment
            **kwargs: Additional payment fields

        Returns:
            Payment object
        """
        try:
            bill = Bill.objects.get(id=bill_id)

            # Validate payment
            if bill.payment_status in ["paid", "cancelled", "refunded"]:
                raise BusinessRuleError(
                    detail=f"Cannot make payment for bill with status: {bill.payment_status}",
                    code="invalid_bill_status",
                )

            if amount > bill.balance_due:
                raise ValidationError(
                    detail=f"Payment amount (${amount}) exceeds balance due (${bill.balance_due})",
                    code="amount_exceeds_balance",
                )

            if amount < Decimal("0.01"):
                raise ValidationError(
                    detail="Payment amount must be at least $0.01",
                    code="invalid_amount",
                )

            # Use patient from bill if not specified
            if patient is None:
                patient = bill.patient

            # Create payment
            payment = Payment.objects.create(
                bill=bill,
                patient=patient,
                amount=amount,
                payment_method=payment_method,
                currency="USD",
                created_by=created_by,
                **kwargs,
            )

            # Process payment based on method
            if payment_method in ["credit_card", "debit_card", "online"]:
                # Process through Stripe
                from .stripe_service import StripeService

                StripeService.create_payment_intent(payment)
            else:
                # Mark as completed for non-online payments
                payment.mark_as_completed()

            logger.info(
                f"Payment created: {payment.payment_number} - "
                f"Bill: {bill.bill_number}, "
                f"Amount: ${amount}"
            )

            return payment

        except Bill.DoesNotExist:
            raise NotFoundError(detail="Bill not found")
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e))
        except Exception as e:
            logger.error(f"Error creating payment: {str(e)}", exc_info=True)
            raise PaymentError(detail="Failed to create payment")

    @staticmethod
    @transaction.atomic
    def create_refund(
        payment_id: int,
        amount: Decimal,
        reason: str = "other",
        reason_details: str = "",
        created_by: Optional[User] = None,
    ) -> Refund:
        """
        Create a refund for a payment

        Args:
            payment_id: Payment ID
            amount: Refund amount
            reason: Refund reason
            reason_details: Refund details
            created_by: User creating refund

        Returns:
            Refund object
        """
        try:
            payment = Payment.objects.get(id=payment_id)

            # Validate refund
            if payment.status != "completed":
                raise BusinessRuleError(
                    detail="Only completed payments can be refunded",
                    code="payment_not_completed",
                )

            if amount > payment.amount:
                raise ValidationError(
                    detail=f"Refund amount (${amount}) exceeds original payment (${payment.amount})",
                    code="amount_exceeds_payment",
                )

            # Check if payment already refunded
            already_refunded = payment.refunds.filter(
                status__in=["completed", "processing"]
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

            if amount > (payment.amount - already_refunded):
                raise ValidationError(
                    detail=f"Refund amount exceeds remaining refundable amount",
                    code="exceeds_refundable",
                )

            # Create refund
            refund = Refund.objects.create(
                payment=payment,
                bill=payment.bill,
                amount=amount,
                reason=reason,
                reason_details=reason_details,
                created_by=created_by,
            )

            # Process refund
            if payment.payment_method in ["credit_card", "debit_card", "online"]:
                # Process through Stripe
                from .stripe_service import StripeService

                StripeService.create_refund(refund)
            else:
                # Mark as completed for non-online payments
                refund.mark_as_completed()
                payment.refund(amount, reason_details)

            logger.info(
                f"Refund created: {refund.refund_number} - "
                f"Payment: {payment.payment_number}, "
                f"Amount: ${amount}"
            )

            return refund

        except Payment.DoesNotExist:
            raise NotFoundError(detail="Payment not found")
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e))
        except Exception as e:
            logger.error(f"Error creating refund: {str(e)}", exc_info=True)
            raise BusinessRuleError(detail="Failed to create refund")

    @staticmethod
    def get_billing_statistics(
        period: str = "month",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        specialist_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get billing statistics for a period

        Args:
            period: Time period (today, week, month, quarter, year)
            start_date: Custom start date
            end_date: Custom end date
            specialist_id: Filter by specialist

        Returns:
            Statistics dictionary
        """
        try:
            # Determine date range
            now = timezone.now()

            if start_date and end_date:
                date_range = {"created_at__range": [start_date, end_date]}
            else:
                if period == "today":
                    date_range = {"created_at__date": now.date()}
                elif period == "week":
                    date_range = {"created_at__gte": now - timedelta(days=7)}
                elif period == "month":
                    date_range = {"created_at__gte": now - timedelta(days=30)}
                elif period == "quarter":
                    date_range = {"created_at__gte": now - timedelta(days=90)}
                elif period == "year":
                    date_range = {"created_at__gte": now - timedelta(days=365)}
                else:
                    date_range = {"created_at__gte": now - timedelta(days=30)}

            # Base querysets
            bills_qs = Bill.objects.filter(**date_range)
            payments_qs = Payment.objects.filter(**date_range)

            if specialist_id:
                bills_qs = bills_qs.filter(appointment__specialist_id=specialist_id)
                payments_qs = payments_qs.filter(
                    bill__appointment__specialist_id=specialist_id
                )

            # Bill statistics
            bill_stats = bills_qs.aggregate(
                total_bills=Count("id"),
                total_amount=Sum("total_amount"),
                total_paid=Sum("amount_paid"),
                total_balance=Sum("balance_due"),
                avg_bill_amount=Avg("total_amount"),
            )

            # Payment statistics
            payment_stats = payments_qs.filter(status="completed").aggregate(
                total_payments=Count("id"),
                total_payment_amount=Sum("amount"),
                avg_payment_amount=Avg("amount"),
            )

            # Status distribution
            status_distribution = (
                bills_qs.values("payment_status")
                .annotate(count=Count("id"), amount=Sum("total_amount"))
                .order_by("payment_status")
            )

            # Overdue bills
            overdue_bills = bills_qs.filter(
                payment_status="overdue", due_date__lt=now.date()
            ).aggregate(count=Count("id"), amount=Sum("balance_due"))

            # Recent activity
            recent_bills = bills_qs.order_by("-created_at")[:5]
            recent_payments = payments_qs.order_by("-payment_date")[:5]

            return {
                "period": period,
                "date_range": date_range,
                "bill_statistics": {
                    "total_bills": bill_stats["total_bills"] or 0,
                    "total_amount": float(bill_stats["total_amount"] or 0),
                    "total_paid": float(bill_stats["total_paid"] or 0),
                    "total_balance": float(bill_stats["total_balance"] or 0),
                    "avg_bill_amount": float(bill_stats["avg_bill_amount"] or 0),
                },
                "payment_statistics": {
                    "total_payments": payment_stats["total_payments"] or 0,
                    "total_payment_amount": float(
                        payment_stats["total_payment_amount"] or 0
                    ),
                    "avg_payment_amount": float(
                        payment_stats["avg_payment_amount"] or 0
                    ),
                },
                "status_distribution": list(status_distribution),
                "overdue_bills": overdue_bills,
                "recent_bills": [
                    {
                        "bill_number": b.bill_number,
                        "patient_name": b.patient.get_full_name(),
                        "total_amount": float(b.total_amount),
                        "status": b.payment_status,
                        "date": b.created_at.date().isoformat(),
                    }
                    for b in recent_bills
                ],
                "recent_payments": [
                    {
                        "payment_number": p.payment_number,
                        "patient_name": p.patient.get_full_name(),
                        "amount": float(p.amount),
                        "method": p.payment_method,
                        "date": p.payment_date.date().isoformat(),
                    }
                    for p in recent_payments
                ],
            }

        except Exception as e:
            logger.error(f"Error getting billing statistics: {str(e)}", exc_info=True)
            raise
