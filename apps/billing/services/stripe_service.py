# services/stripe_service.py
import stripe
from django.conf import settings
import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from apps.core.exceptions.base_exceptions import PaymentError, NotFoundError
from apps.users.models import User
from apps.billing.models import Payment, Refund

logger = logging.getLogger(__name__)


class StripeService:
    """Service for Stripe payment processing"""

    def __init__(self):
        """Initialize Stripe with API key"""
        if hasattr(settings, "STRIPE_SECRET_KEY"):
            stripe.api_key = settings.STRIPE_SECRET_KEY
        else:
            logger.warning("STRIPE_SECRET_KEY not found in settings")

    @staticmethod
    def create_payment_intent(payment: Payment) -> Dict[str, Any]:
        """
        Create Stripe Payment Intent for a payment

        Args:
            payment: Payment object

        Returns:
            Stripe Payment Intent response
        """
        try:
            # Create or get Stripe customer
            customer_id = StripeService._get_or_create_customer(payment.patient)

            # Create payment intent
            intent_data = {
                "amount": int(payment.amount * 100),  # Convert to cents
                "currency": "usd",  # Always use USD
                "customer": customer_id,
                "metadata": {
                    "payment_id": str(payment.id),
                    "bill_id": str(payment.bill.id),
                    "patient_id": str(payment.patient.id),
                    "bill_number": payment.bill.bill_number,
                },
                "description": f"Payment for bill {payment.bill.bill_number}",
                "setup_future_usage": "off_session",  # Allow future payments
            }

            # Add payment method if saved
            if (
                hasattr(payment, "stripe_payment_method_id")
                and payment.stripe_payment_method_id
            ):
                intent_data["payment_method"] = payment.stripe_payment_method_id
                intent_data["off_session"] = True
                intent_data["confirm"] = True

            # Create intent
            intent = stripe.PaymentIntent.create(**intent_data)

            # Update payment with Stripe data
            payment.stripe_payment_intent_id = intent.id
            payment.status = "processing"
            payment.save()

            logger.info(
                f"Stripe Payment Intent created: {intent.id} for payment {payment.id}"
            )

            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "status": intent.status,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {str(e)}")
            payment.mark_as_failed(str(e))
            raise PaymentError(detail=f"Payment processing failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}", exc_info=True)
            raise PaymentError(detail="Failed to process payment")

    @staticmethod
    def confirm_payment_intent(payment_intent_id: str) -> Dict[str, Any]:
        """
        Confirm a Stripe Payment Intent

        Args:
            payment_intent_id: Stripe Payment Intent ID

        Returns:
            Confirmation response
        """
        try:
            # Retrieve payment intent
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            # Confirm if not already confirmed
            if intent.status in ["requires_confirmation", "requires_action"]:
                intent = stripe.PaymentIntent.confirm(payment_intent_id)

            # Update payment status
            try:
                payment = Payment.objects.get(
                    stripe_payment_intent_id=payment_intent_id
                )
            except Payment.DoesNotExist:
                logger.error(f"Payment not found for intent: {payment_intent_id}")
                raise NotFoundError(detail="Payment not found")

            if intent.status == "succeeded":
                # Update payment
                payment.status = "completed"
                payment.processed_at = timezone.now()
                payment.stripe_charge_id = (
                    intent.charges.data[0].id if intent.charges.data else None
                )

                # Save card details if available
                if intent.payment_method and hasattr(intent.payment_method, "card"):
                    payment.card_last4 = intent.payment_method.card.last4
                    payment.card_brand = intent.payment_method.card.brand
                    payment.card_exp_month = intent.payment_method.card.exp_month
                    payment.card_exp_year = intent.payment_method.card.exp_year

                payment.save()

                # Update bill status
                payment.bill.invoice_status = (
                    "paid" if payment.bill.balance_due <= 0 else "sent"
                )
                payment.bill.save()

                logger.info(f"Payment confirmed: {payment_intent_id}")

            return {
                "status": intent.status,
                "payment_id": payment.id,
                "bill_id": payment.bill.id,
                "bill_number": payment.bill.bill_number,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error confirming payment intent: {str(e)}")
            raise PaymentError(detail=f"Payment confirmation failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error confirming payment intent: {str(e)}", exc_info=True)
            raise PaymentError(detail="Failed to confirm payment")

    @staticmethod
    def create_refund(refund: Refund) -> Dict[str, Any]:
        """
        Create Stripe refund

        Args:
            refund: Refund object

        Returns:
            Stripe refund response
        """
        try:
            # Get payment
            payment = refund.payment

            if not payment.stripe_charge_id:
                raise PaymentError(detail="No Stripe charge found for refund")

            # Create refund
            stripe_refund = stripe.Refund.create(
                charge=payment.stripe_charge_id,
                amount=int(refund.amount * 100),  # Convert to cents
                metadata={
                    "refund_id": str(refund.id),
                    "payment_id": str(payment.id),
                    "bill_id": str(refund.bill.id),
                },
                reason=(
                    "requested_by_customer"
                    if refund.reason == "requested_by_customer"
                    else "other"
                ),
            )

            # Update refund
            refund.stripe_refund_id = stripe_refund.id
            refund.status = "completed"
            refund.save()

            # Update payment status
            payment.status = "refunded"
            payment.refunded_at = timezone.now()
            payment.save()

            logger.info(
                f"Stripe refund created: {stripe_refund.id} for refund {refund.id}"
            )

            return {
                "refund_id": stripe_refund.id,
                "status": stripe_refund.status,
                "amount": stripe_refund.amount / 100,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating refund: {str(e)}")
            refund.status = "failed"
            refund.save()
            raise PaymentError(detail=f"Refund failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating refund: {str(e)}", exc_info=True)
            raise PaymentError(detail="Failed to process refund")

    @staticmethod
    def _get_or_create_customer(patient: User) -> str:
        """
        Get or create Stripe customer for patient

        Args:
            patient: User object

        Returns:
            Stripe customer ID

        Raises:
            PaymentError: If customer creation fails
        """
        try:
            # Check if customer already exists
            if hasattr(patient, "stripe_customer_id") and patient.stripe_customer_id:
                # Verify customer exists in Stripe
                try:
                    customer = stripe.Customer.retrieve(patient.stripe_customer_id)
                    return customer.id
                except stripe.error.InvalidRequestError:
                    # Customer doesn't exist in Stripe, create new one
                    logger.warning(
                        f"Stripe customer {patient.stripe_customer_id} not found, creating new"
                    )
                    pass

            # Create new customer
            customer_data = {
                "email": patient.email,
                "name": patient.get_full_name(),
                "phone": patient.phone,
                "metadata": {
                    "user_id": str(patient.id),
                    "user_type": patient.user_type,
                },
            }

            # Add address if available
            if hasattr(patient, "address"):
                customer_data["address"] = {
                    "line1": patient.address,
                    "city": patient.city if hasattr(patient, "city") else "",
                    "state": patient.state if hasattr(patient, "state") else "",
                    "postal_code": (
                        patient.zip_code if hasattr(patient, "zip_code") else ""
                    ),
                }

            customer = stripe.Customer.create(**customer_data)

            # Save customer ID to user profile
            patient.stripe_customer_id = customer.id
            patient.save(update_fields=["stripe_customer_id"])

            logger.info(f"Created Stripe customer: {customer.id} for user {patient.id}")

            return customer.id

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating customer: {str(e)}")
            raise PaymentError(detail="Failed to create payment customer")
        except Exception as e:
            logger.error(f"Error creating customer: {str(e)}", exc_info=True)
            raise PaymentError(detail="Failed to create customer")

    @staticmethod
    def handle_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
        """
        Handle Stripe webhook events

        Args:
            payload: Webhook payload
            sig_header: Stripe signature header

        Returns:
            Webhook processing result

        Raises:
            PaymentError: If webhook processing fails
        """
        try:
            # Verify webhook signature
            if not hasattr(settings, "STRIPE_WEBHOOK_SECRET"):
                raise PaymentError(detail="Stripe webhook secret not configured")

            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )

            # Handle event
            event_type = event["type"]
            event_data = event["data"]["object"]

            logger.info(f"Stripe webhook received: {event_type}")

            if event_type == "payment_intent.succeeded":
                return StripeService._handle_payment_intent_succeeded(event_data)
            elif event_type == "payment_intent.payment_failed":
                return StripeService._handle_payment_intent_failed(event_data)
            elif event_type == "charge.refunded":
                return StripeService._handle_charge_refunded(event_data)
            elif event_type == "customer.subscription.deleted":
                return StripeService._handle_subscription_deleted(event_data)
            else:
                logger.info(f"Unhandled Stripe event type: {event_type}")
                return {"status": "ignored", "event_type": event_type}

        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid Stripe webhook signature: {str(e)}")
            raise PaymentError(detail="Invalid webhook signature")
        except Exception as e:
            logger.error(f"Error handling Stripe webhook: {str(e)}", exc_info=True)
            raise PaymentError(detail="Failed to process webhook")

    @staticmethod
    def _handle_payment_intent_succeeded(event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment intent"""
        payment_intent_id = event_data["id"]

        try:
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent_id)

            # Update payment
            payment.status = "completed"
            payment.processed_at = timezone.now()
            payment.stripe_charge_id = (
                event_data.get("charges", {}).get("data", [{}])[0].get("id")
            )
            payment.save()

            # Update bill status
            payment.bill.invoice_status = (
                "paid" if payment.bill.balance_due <= 0 else "sent"
            )
            payment.bill.save()

            logger.info(f"Payment completed via webhook: {payment_intent_id}")

            return {
                "status": "processed",
                "payment_id": payment.id,
                "bill_id": payment.bill.id,
                "payment_number": payment.payment_number,
            }

        except Payment.DoesNotExist:
            logger.error(f"Payment not found for intent: {payment_intent_id}")
            return {"status": "error", "message": "Payment not found"}

    @staticmethod
    def _handle_payment_intent_failed(event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment intent"""
        payment_intent_id = event_data["id"]
        error_message = event_data.get("last_payment_error", {}).get(
            "message", "Unknown error"
        )

        try:
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent_id)
            payment.mark_as_failed(error_message)

            logger.warning(f"Payment failed via webhook: {payment_intent_id}")

            return {
                "status": "processed",
                "payment_id": payment.id,
                "error": error_message,
            }

        except Payment.DoesNotExist:
            logger.error(f"Payment not found for intent: {payment_intent_id}")
            return {"status": "error", "message": "Payment not found"}

    @staticmethod
    def _handle_charge_refunded(event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle charge refunded"""
        charge_id = event_data["id"]

        try:
            # Find payment with this charge
            payment = Payment.objects.get(stripe_charge_id=charge_id)

            # Find or create refund record
            refund_amount = Decimal(event_data.get("amount_refunded", 0)) / 100
            refund_id = event_data.get("refunds", {}).get("data", [{}])[0].get("id")

            if refund_id:
                refund, created = Refund.objects.get_or_create(
                    stripe_refund_id=refund_id,
                    defaults={
                        "payment": payment,
                        "bill": payment.bill,
                        "amount": refund_amount,
                        "reason": "requested_by_customer",
                        "status": "completed",
                    },
                )

                if not created:
                    refund.status = "completed"
                    refund.save()

                # Update payment
                payment.status = "refunded"
                payment.refunded_at = timezone.now()
                payment.save()

                logger.info(f"Refund processed via webhook: {refund_id}")

                return {
                    "status": "processed",
                    "refund_id": refund.id,
                    "payment_id": payment.id,
                }

            return {"status": "ignored", "reason": "No refund ID found"}

        except Payment.DoesNotExist:
            logger.error(f"Payment not found for charge: {charge_id}")
            return {"status": "error", "message": "Payment not found"}

    @staticmethod
    def _handle_subscription_deleted(event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle subscription deleted"""
        customer_id = event_data.get("customer")

        # Update user's saved payment methods if needed
        # This is a placeholder for subscription handling

        logger.info(f"Subscription deleted for customer: {customer_id}")

        return {
            "status": "processed",
            "customer_id": customer_id,
            "action": "subscription_deleted",
        }

    @staticmethod
    def get_payment_intent_status(payment_intent_id: str) -> Dict[str, Any]:
        """
        Get status of a payment intent

        Args:
            payment_intent_id: Stripe Payment Intent ID

        Returns:
            Payment intent status
        """
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            return {
                "status": intent.status,
                "amount": intent.amount / 100,
                "currency": intent.currency,
                "customer": intent.customer,
                "created": intent.created,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error retrieving payment intent: {str(e)}")
            raise PaymentError(detail=f"Failed to get payment status: {str(e)}")
