import stripe
from django.conf import settings
import logging
from typing import Dict, Any
from apps.core.exceptions.base_exceptions import PaymentError, NotFoundError
from apps.users.models import User
from apps.billing.models import Payment, Refund

logger = logging.getLogger(__name__)


class StripeService:
    """Service for Stripe payment processing"""

    # Initialize Stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    @staticmethod
    def create_payment_intent(payment: "Payment") -> Dict[str, Any]:
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
                "currency": payment.currency.lower(),
                "customer": customer_id,
                "metadata": {
                    "payment_id": payment.id,
                    "bill_id": payment.bill.id,
                    "patient_id": str(payment.patient.user_id),
                    "bill_number": payment.bill.bill_number,
                },
                "description": f"Payment for bill {payment.bill.bill_number}",
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

            logger.info(f"Stripe Payment Intent created: {intent.id}")

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
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent_id)

            if intent.status == "succeeded":
                payment.mark_as_completed()
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

                logger.info(f"Payment confirmed: {payment_intent_id}")

            return {
                "status": intent.status,
                "payment_id": payment.id,
                "bill_id": payment.bill.id,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error confirming payment intent: {str(e)}")
            raise PaymentError(detail=f"Payment confirmation failed: {str(e)}")
        except Payment.DoesNotExist:
            raise NotFoundError(detail="Payment not found")
        except Exception as e:
            logger.error(f"Error confirming payment intent: {str(e)}", exc_info=True)
            raise PaymentError(detail="Failed to confirm payment")

    @staticmethod
    def create_refund(refund: "Refund") -> Dict[str, Any]:
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
                    "refund_id": refund.id,
                    "payment_id": payment.id,
                    "bill_id": refund.bill.id,
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

            # Update payment
            payment.refund(refund.amount, refund.reason_details)

            logger.info(f"Stripe refund created: {stripe_refund.id}")

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
                    pass

            # Create new customer
            customer_data = {
                "email": patient.email,
                "name": patient.get_full_name(),
                "phone": patient.phone,
                "metadata": {
                    "user_id": str(patient.user_id),
                    "user_type": patient.user_type,
                },
            }

            customer = stripe.Customer.create(**customer_data)

            # Save customer ID to user profile
            patient.stripe_customer_id = customer.id
            patient.save(update_fields=["stripe_customer_id"])

            return customer.id

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating customer: {str(e)}")
            raise PaymentError(detail="Failed to create payment customer")

    @staticmethod
    def handle_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
        """
        Handle Stripe webhook events

        Args:
            payload: Webhook payload
            sig_header: Stripe signature header

        Returns:
            Webhook processing result
        """
        try:
            # Verify webhook signature
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
            elif event_type == "invoice.payment_succeeded":
                return StripeService._handle_invoice_payment_succeeded(event_data)
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
            payment.mark_as_completed()

            # Update bill
            payment.bill.mark_as_paid(
                amount=payment.amount,
                payment_method=payment.payment_method,
                notes=f"Stripe payment: {payment_intent_id}",
            )

            logger.info(f"Payment completed via webhook: {payment_intent_id}")

            return {
                "status": "processed",
                "payment_id": payment.id,
                "bill_id": payment.bill.id,
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
