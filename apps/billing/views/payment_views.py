from decimal import Decimal
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt


from apps.billing.models.payment_models import Payment
from apps.billing.models.payment_models import Payment
from django.core.exceptions import PermissionDenied
from apps.billing.serializers.payment import (
    PaymentSerializer,
    PaymentCreateSerializer,
    CreatePaymentIntentSerializer,
)
from apps.billing.services.billing_service import BillingService
from apps.billing.services.stripe_service import StripeService
from apps.core.responses.api_response import APIResponse
from apps.core.decorators.error_handler import api_error_handler
from apps.core.decorators.rate_limit import rate_limit
from apps.billing.models.payment_models import PaymentMethod
from apps.billing.serializers.payment import PaymentMethodSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    """
    Unified ViewSet to handle payment operations
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get queryset with access control"""
        user = self.request.user
        queryset = Payment.objects.select_related("bill", "patient", "created_by").all()

        # Apply role-based filtering
        if user.user_type == "patient":
            queryset = queryset.filter(patient=user)
        elif user.user_type == "specialist":
            if hasattr(user, "specialist_profile"):
                queryset = queryset.filter(
                    bill__appointment__specialist=user.specialist_profile
                )

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return PaymentCreateSerializer
        return PaymentSerializer

    @api_error_handler
    @rate_limit(profile="PAYMENT", scope="payment_create")
    def create(self, request, *args, **kwargs):
        """Create payment"""
        # Check permissions
        if request.user.user_type not in ["patient", "admin", "staff"]:
            raise PermissionDenied("Only patients, admin, or staff can create payments")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Use service for business logic
        payment = BillingService.create_payment(
            bill_id=serializer.validated_data["bill_id"],
            amount=serializer.validated_data["amount"],
            payment_method=serializer.validated_data["payment_method"],
            created_by=request.user,
            **serializer.validated_data,
        )

        return APIResponse.created(
            message="Payment created successfully",
            data=PaymentSerializer(payment).data,
        )

    @api_error_handler
    @rate_limit(profile="PAYMENT", scope="payment_intent")
    @action(detail=False, methods=["post"], url_path="create-intent")
    def create_payment_intent(self, request):
        """Create Stripe Payment Intent"""
        # Check permissions
        if request.user.user_type not in ["patient", "admin", "staff"]:
            raise PermissionDenied(
                "Only patients, admin, or staff can create payment intents"
            )

        serializer = CreatePaymentIntentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        bill = serializer.validated_data["bill"]
        amount = serializer.validated_data["amount"]

        # For patients, ensure they're paying their own bill
        if request.user.user_type == "patient" and bill.patient != request.user:
            raise PermissionDenied("Cannot make payment for another patient's bill")

        # Create payment record
        payment = Payment.objects.create(
            bill=bill,
            patient=(
                request.user if request.user.user_type == "patient" else bill.patient
            ),
            amount=amount,
            payment_method="online",
            currency="USD",
            created_by=request.user,
        )

        # Create Stripe Payment Intent
        result = StripeService.create_payment_intent(payment)

        return APIResponse.success(
            message="Payment intent created",
            data={
                "payment_id": payment.id,
                "client_secret": result["client_secret"],
                "payment_intent_id": result["payment_intent_id"],
                "status": result["status"],
                "amount": float(amount),
                "bill_number": bill.bill_number,
            },
        )

    @api_error_handler
    @rate_limit(profile="PAYMENT", scope="payment_confirm")
    @action(
        detail=False,
        methods=["post"],
        url_path="confirm-intent/(?P<payment_intent_id>[^/.]+)",
    )
    def confirm_payment_intent(self, request, payment_intent_id=None):
        """Confirm Stripe Payment Intent"""
        result = StripeService.confirm_payment_intent(payment_intent_id)

        if result["status"] == "succeeded":
            return APIResponse.success(
                message="Payment confirmed successfully", data=result
            )
        else:
            return APIResponse.error(
                message=f"Payment confirmation failed: {result.get('status')}",
                code="payment_confirmation_failed",
                data=result,
            )


# ====================== STRIPE WEBHOOK VIEW ======================


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookViewSet(viewsets.ViewSet):
    """
    ViewSet for Stripe webhook handling
    """

    permission_classes = [AllowAny]

    @method_decorator(csrf_exempt)
    @api_error_handler
    def create(self, request):
        """Handle Stripe webhook"""
        import json

        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        result = StripeService.handle_webhook(payload, sig_header)

        return APIResponse.success(
            message="Webhook processed successfully", data=result
        )


class PaymentMethodViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payment methods
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get user's payment methods"""
        return PaymentMethod.objects.filter(
            patient=self.request.user, is_active=True
        ).order_by("-is_default", "-created_at")

    def get_serializer_class(self):
        return PaymentMethodSerializer

    @api_error_handler
    def list(self, request, *args, **kwargs):
        """Get user's payment methods"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        return APIResponse.success(
            message="Payment methods retrieved", data=serializer.data
        )
