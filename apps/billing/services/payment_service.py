# services/payment_service.py
import logging
from typing import Dict, Optional
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import QuerySet, Sum
from apps.core.exceptions.base_exceptions import (
    AuthorizationError,
    NotFoundError,
    BusinessRuleError,
    PaymentError,
)
from apps.billing.models import Payment, PaymentMethod, Refund
from apps.users.models import User

logger = logging.getLogger(__name__)


class PaymentService:
    """Service for handling payment-related operations"""

    @staticmethod
    def get_filtered_queryset(user: User) -> QuerySet[Payment]:
        """
        Get payment queryset with access control

        Args:
            user: Authenticated user

        Returns:
            Filtered QuerySet of payments
        """
        if not user.is_authenticated:
            return Payment.objects.none()

        queryset = Payment.objects.select_related(
            "bill",
            "patient",
            "created_by",
            "bill__appointment",
            "bill__appointment__specialist",
        ).prefetch_related("refunds")

        if user.user_type == "patient":
            queryset = queryset.filter(patient=user)
        elif user.user_type == "specialist":
            if hasattr(user, "specialist_profile"):
                queryset = queryset.filter(
                    bill__appointment__specialist=user.specialist_profile
                )
        # Admin and staff see all payments

        return queryset

    @staticmethod
    def get_payment_methods(user: User) -> QuerySet[PaymentMethod]:
        """
        Get payment methods for user

        Args:
            user: User to get payment methods for

        Returns:
            QuerySet of payment methods
        """
        if not user.is_authenticated:
            return PaymentMethod.objects.none()

        return PaymentMethod.objects.filter(patient=user, is_active=True).order_by(
            "-is_default", "-created_at"
        )

    @classmethod
    @transaction.atomic
    def create_cash_payment(
        cls, bill_id: int, amount: Decimal, created_by: User, notes: str = ""
    ) -> Payment:
        """
        Create a cash payment

        Args:
            bill_id: ID of bill to pay
            amount: Payment amount
            created_by: User creating payment
            notes: Additional notes

        Returns:
            Created Payment instance
        """
        from apps.billing.services.billing_service import BillingService

        return BillingService.create_payment(
            bill_id=bill_id,
            amount=amount,
            payment_method="cash",
            created_by=created_by,
            notes=notes,
        )

    @classmethod
    @transaction.atomic
    def create_bank_transfer_payment(
        cls,
        bill_id: int,
        amount: Decimal,
        bank_reference: str,
        bank_name: str,
        created_by: User,
        notes: str = "",
    ) -> Payment:
        """
        Create a bank transfer payment

        Args:
            bill_id: ID of bill to pay
            amount: Payment amount
            bank_reference: Bank transaction reference
            bank_name: Name of bank
            created_by: User creating payment
            notes: Additional notes

        Returns:
            Created Payment instance
        """
        from apps.billing.services.billing_service import BillingService

        return BillingService.create_payment(
            bill_id=bill_id,
            amount=amount,
            payment_method="bank_transfer",
            created_by=created_by,
            notes=notes,
            bank_reference=bank_reference,
            bank_name=bank_name,
        )

    @classmethod
    @transaction.atomic
    def create_online_payment(
        cls,
        bill_id: int,
        amount: Decimal,
        created_by: User,
        stripe_payment_method_id: Optional[str] = None,
        notes: str = "",
    ) -> Payment:
        """
        Create an online payment (Stripe)

        Args:
            bill_id: ID of bill to pay
            amount: Payment amount
            created_by: User creating payment
            stripe_payment_method_id: Optional Stripe payment method ID
            notes: Additional notes

        Returns:
            Created Payment instance
        """
        from apps.billing.services.billing_service import BillingService

        payment_data = {
            "bill_id": bill_id,
            "amount": amount,
            "payment_method": "online",
            "created_by": created_by,
            "notes": notes,
        }

        if stripe_payment_method_id:
            payment_data["stripe_payment_method_id"] = stripe_payment_method_id

        return BillingService.create_payment(**payment_data)

    @staticmethod
    @transaction.atomic
    def process_refund(
        payment_id: int,
        amount: Decimal,
        reason: str,
        reason_details: str = "",
        created_by: User = None,
    ) -> Refund:
        """
        Process a refund for a payment

        Args:
            payment_id: ID of payment to refund
            amount: Refund amount
            reason: Refund reason
            reason_details: Detailed reason
            created_by: User processing refund

        Returns:
            Created Refund instance

        Raises:
            NotFoundError: If payment not found
            BusinessRuleError: If validation fails
        """
        try:
            payment = Payment.objects.select_related("bill").get(id=payment_id)
        except Payment.DoesNotExist:
            raise NotFoundError(detail="Payment not found")

        # Validate refund
        if payment.status != "completed":
            raise BusinessRuleError(
                detail=f"Cannot refund payment with status: {payment.status}"
            )

        if amount > payment.amount:
            raise BusinessRuleError(
                detail=f"Refund amount (${amount}) exceeds original payment amount (${payment.amount})"
            )

        # Calculate already refunded amount
        already_refunded = payment.refunds.filter(status="completed").aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")

        if amount > (payment.amount - already_refunded):
            raise BusinessRuleError(
                detail=f"Refund amount exceeds remaining refundable amount"
            )

        # Create refund
        refund = Refund.objects.create(
            payment=payment,
            bill=payment.bill,
            amount=amount,
            reason=reason,
            reason_details=reason_details,
            status="requested",
            created_by=created_by,
        )

        # If it's a Stripe payment, process via Stripe
        if payment.payment_method == "online" and payment.stripe_charge_id:
            try:
                from apps.billing.services.stripe_service import StripeService

                stripe_result = StripeService.create_refund(refund)
                refund.status = "completed"
                refund.stripe_refund_id = stripe_result.get("refund_id")
                refund.save()

                # Update payment status
                payment.refund(amount, reason_details)

            except PaymentError as e:
                logger.error(f"Stripe refund failed: {str(e)}")
                refund.status = "failed"
                refund.save()
                raise
        else:
            # For non-Stripe payments, mark as completed immediately
            refund.status = "completed"
            refund.save()

            # Update payment
            payment.refund(amount, reason_details)

        logger.info(
            f"Refund processed: {refund.refund_number} for payment {payment.payment_number}, "
            f"amount: ${amount}, reason: {reason}"
        )

        return refund

    @staticmethod
    def get_payment_summary(payment: Payment) -> Dict:
        """
        Get detailed summary of a payment

        Args:
            payment: Payment instance

        Returns:
            Dictionary with payment summary
        """
        refunds = payment.refunds.filter(status="completed")
        total_refunded = refunds.aggregate(total=Sum("amount"))["total"] or Decimal("0")

        return {
            "payment": {
                "id": payment.id,
                "payment_number": payment.payment_number,
                "amount": float(payment.amount),
                "payment_method": payment.payment_method,
                "status": payment.status,
                "payment_date": payment.payment_date,
                "bank_reference": payment.bank_reference,
                "notes": payment.notes,
            },
            "bill": {
                "bill_number": payment.bill.bill_number,
                "total_amount": float(payment.bill.total_amount),
                "balance_due": float(payment.bill.balance_due),
            },
            "patient": {
                "id": payment.patient.id,
                "name": payment.patient.get_full_name(),
                "email": payment.patient.email,
            },
            "refunds": {
                "total_refunded": float(total_refunded),
                "remaining_amount": float(payment.amount - total_refunded),
                "refunds_count": refunds.count(),
                "refunds_list": list(
                    refunds.values("refund_number", "amount", "reason", "status")
                ),
            },
        }

    @classmethod
    @transaction.atomic
    def create_payment_method(cls, patient: User, **method_data) -> PaymentMethod:
        """
        Create a payment method for patient

        Args:
            patient: Patient user
            **method_data: Payment method details

        Returns:
            Created PaymentMethod instance
        """
        # If setting as default, unset other defaults
        if method_data.get("is_default", False):
            PaymentMethod.objects.filter(patient=patient, is_default=True).update(
                is_default=False
            )

        method_data["patient"] = patient
        payment_method = PaymentMethod.objects.create(**method_data)

        logger.info(f"Payment method created for patient {patient.id}")

        return payment_method

    @classmethod
    @transaction.atomic
    def update_payment_method(
        cls, payment_method: PaymentMethod, **update_data
    ) -> PaymentMethod:
        """
        Update payment method

        Args:
            payment_method: PaymentMethod instance to update
            **update_data: Fields to update

        Returns:
            Updated PaymentMethod instance
        """
        # Only allow updating certain fields
        allowed_fields = ["is_default", "is_active"]

        for field in allowed_fields:
            if field in update_data:
                value = update_data[field]

                # Handle default payment method
                if field == "is_default" and value:
                    PaymentMethod.objects.filter(
                        patient=payment_method.patient, is_default=True
                    ).update(is_default=False)

                setattr(payment_method, field, value)

        payment_method.save()

        logger.info(f"Payment method {payment_method.id} updated")

        return payment_method

    @classmethod
    @transaction.atomic
    def set_default_payment_method(cls, payment_method: PaymentMethod) -> PaymentMethod:
        """
        Set payment method as default

        Args:
            payment_method: PaymentMethod to set as default

        Returns:
            Updated PaymentMethod instance
        """
        # Unset default from other methods
        PaymentMethod.objects.filter(
            patient=payment_method.patient, is_default=True
        ).update(is_default=False)

        # Set this as default
        payment_method.is_default = True
        payment_method.save()

        logger.info(f"Payment method {payment_method.id} set as default")

        return payment_method

    @classmethod
    @transaction.atomic
    def create_online_payment(
        cls, bill_id: int, amount: Decimal, user: User
    ) -> Payment:
        """
        Create online payment and Stripe payment intent

        Args:
            bill_id: Bill ID
            amount: Payment amount
            user: User creating payment

        Returns:
            Created Payment instance
        """
        from apps.billing.models import Bill
        from apps.billing.services.stripe_service import StripeService

        try:
            bill = Bill.objects.select_related("patient").get(id=bill_id)
        except Bill.DoesNotExist:
            raise NotFoundError(detail="Bill not found")

        # Permission check
        if user.user_type == "patient" and bill.patient != user:
            raise AuthorizationError(
                detail="You can only make payments for your own bills"
            )

        # Validate amount
        from apps.billing.services.billing_service import BillingService

        if amount < BillingService.MIN_PAYMENT_AMOUNT:
            raise BusinessRuleError(
                detail=f"Minimum payment amount is ${BillingService.MIN_PAYMENT_AMOUNT}"
            )

        if amount > bill.balance_due:
            raise BusinessRuleError(
                detail=f"Payment amount exceeds balance due (${bill.balance_due})"
            )

        # Create payment record
        payment = Payment.objects.create(
            bill=bill,
            patient=bill.patient,
            amount=amount,
            payment_method="online",
            status="pending",
            created_by=user,
        )

        # Create Stripe payment intent
        try:
            stripe_result = StripeService().create_payment_intent(payment)
            return payment
        except PaymentError as e:
            payment.delete()
            raise

    @staticmethod
    def confirm_online_payment(payment_intent_id: str) -> Dict:
        """
        Confirm Stripe payment intent

        Args:
            payment_intent_id: Stripe payment intent ID

        Returns:
            Confirmation result
        """
        from apps.billing.services.stripe_service import StripeService

        return StripeService().confirm_payment_intent(payment_intent_id)

    @classmethod
    @transaction.atomic
    def mark_refund_completed(cls, refund: Refund, user: User = None) -> Refund:
        """
        Mark refund as completed

        Args:
            refund: Refund instance
            user: User marking refund as completed

        Returns:
            Updated Refund instance

        Raises:
            BusinessRuleError: If refund cannot be marked as completed
        """
        if refund.status == "completed":
            raise BusinessRuleError(detail="Refund is already completed")

        refund.status = "completed"
        refund.processed_date = timezone.now().date()
        refund.save()

        logger.info(f"Refund {refund.refund_number} marked as completed")

        return refund
