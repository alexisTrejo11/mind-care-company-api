from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.permissions import IsAdminOrStaff, IsPatient
from apps.core.exceptions.base_exceptions import ValidationError
from apps.core.decorators.error_handler import api_error_handler
from apps.core.decorators.rate_limit import rate_limit
from apps.core.responses.api_response import APIResponse

from apps.billing.services import BillingService, PaymentService
from apps.billing.models import Refund, InsuranceClaim
from apps.billing.serializers import (
    PaymentCreateSerializer,
    OnlinePaymentIntentSerializer,
    PaymentMethodSerializer,
    RefundCreateSerializer,
    RefundSerializer,
    PaymentFilterSerializer,
    PaymentSerializer,
    InsuranceClaimCreateSerializer,
    InsuranceClaimSerializer,
)


class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payments

    Supports filtering by:
    - start_date, end_date: Payment date range
    - payment_method: Cash, bank transfer, online, etc.
    - status: pending, completed, failed, refunded
    - patient_id: Filter by patient
    - bill_id: Filter by bill
    - min_amount, max_amount: Amount range
    """

    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]
    ordering_fields = [
        "payment_date",
        "amount",
        "created_at",
    ]
    ordering = ["-payment_date"]
    search_fields = [
        "payment_number",
        "patient__first_name",
        "patient__last_name",
        "patient__email",
        "bank_reference",
        "notes",
    ]

    def get_permissions(self):
        """Assign permissions based on action"""
        if self.action in ["create", "create_online_intent", "confirm_online_payment"]:
            return [IsPatient() | IsAdminOrStaff()]
        elif self.action in ["verify_bank_transfer", "process_refund"]:
            return [IsAdminOrStaff()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """Get filtered queryset based on user permissions"""
        return PaymentService.get_filtered_queryset(self.request.user)

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return PaymentCreateSerializer
        elif self.action == "create_online_intent":
            return OnlinePaymentIntentSerializer
        elif self.action == "process_refund":
            return RefundCreateSerializer
        return PaymentSerializer

    @api_error_handler
    @rate_limit(profile="READ_OPERATION", scope="payment_list")
    def list(self, request, *args, **kwargs):
        """List payments with filtering"""
        filter_serializer = PaymentFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return APIResponse.from_paginated_response(
                paginator=self.paginator,
                data=serializer.data,
                message="Payments retrieved successfully",
            )

        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(
            message="Payments retrieved successfully",
            data=serializer.data,
        )

    @api_error_handler
    @rate_limit(profile="READ_OPERATION", scope="payment_detail")
    def retrieve(self, request, *args, **kwargs):
        """Get payment details"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # Get detailed summary for payment
        summary = PaymentService.get_payment_summary(instance)

        return APIResponse.success(
            message="Payment details retrieved",
            data={
                "payment": serializer.data,
                "summary": summary,
            },
        )

    @api_error_handler
    @rate_limit(profile="WRITE_OPERATION", scope="payment_create")
    def create(self, request, *args, **kwargs):
        """Create payment (generic - for admin/staff)"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create payment using service layer
        from apps.billing.services.billing_service import BillingService

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
    @action(detail=False, methods=["post"], url_path="online/intent")
    @rate_limit(profile="WRITE_OPERATION", scope="online_payment_intent")
    def create_online_intent(self, request):
        """Create Stripe payment intent for online payment"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Use service layer to create online payment with Stripe intent
        payment = PaymentService.create_online_payment(
            bill_id=serializer.validated_data["bill_id"],
            amount=serializer.validated_data["amount"],
            user=request.user,
        )

        # Get Stripe intent details
        from apps.billing.services.stripe_service import StripeService

        stripe_result = StripeService().get_payment_intent_status(
            payment.stripe_payment_intent_id
        )

        return APIResponse.success(
            message="Payment intent created",
            data={
                "payment_id": payment.id,
                "payment_number": payment.payment_number,
                "client_secret": stripe_result.get("client_secret"),
                "payment_intent_id": payment.stripe_payment_intent_id,
                "status": stripe_result.get("status"),
                "amount": float(payment.amount),
                "bill_number": payment.bill.bill_number,
            },
        )

    @api_error_handler
    @action(
        detail=False,
        methods=["post"],
        url_path="online/confirm/(?P<payment_intent_id>[^/.]+)",
    )
    @rate_limit(profile="WRITE_OPERATION", scope="confirm_online_payment")
    def confirm_online_payment(self, request, payment_intent_id=None):
        """Confirm Stripe payment intent"""
        # Use service layer to confirm payment
        result = PaymentService.confirm_online_payment(payment_intent_id)

        if result.get("status") == "succeeded":
            return APIResponse.success(
                message="Payment confirmed successfully", data=result
            )
        else:
            return APIResponse.error(
                message=f"Payment confirmation failed: {result.get('status')}",
                code="payment_confirmation_failed",
                metadata=result,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="verify-bank-transfer")
    @rate_limit(profile="WRITE_OPERATION", scope="verify_bank_transfer")
    def verify_bank_transfer(self, request, pk=None):
        """Verify and complete a bank transfer payment (admin/staff only)"""
        instance = self.get_object()

        if instance.payment_method != "bank_transfer":
            raise ValidationError("Only bank transfer payments can be verified")

        notes = request.data.get("notes", "")

        payment = BillingService.verify_bank_transfer_payment(
            payment_id=instance.id,
            verified_by=request.user,
            notes=notes,
        )

        return APIResponse.success(
            message="Bank transfer payment verified successfully",
            data=PaymentSerializer(payment).data,
        )

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="refunds")
    @rate_limit(profile="WRITE_OPERATION", scope="process_refund")
    def process_refund(self, request, pk=None):
        """Process refund for payment (admin/staff only)"""
        instance = self.get_object()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refund = PaymentService.process_refund(
            payment_id=instance.id,
            amount=serializer.validated_data["amount"],
            reason=serializer.validated_data["reason"],
            reason_details=serializer.validated_data.get("reason_details", ""),
            created_by=request.user,
        )

        return APIResponse.created(
            message="Refund processed successfully",
            data=RefundSerializer(refund).data,
        )

    @api_error_handler
    @action(detail=True, methods=["get"], url_path="refunds")
    @rate_limit(profile="READ_OPERATION", scope="payment_refunds")
    def list_refunds(self, request, pk=None):
        """List refunds for payment"""
        instance = self.get_object()
        refunds = instance.refunds.all()

        serializer = RefundSerializer(refunds, many=True)
        return APIResponse.success(
            message="Refunds retrieved",
            data=serializer.data,
        )


class PaymentMethodViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payment methods
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get user's payment methods"""
        return PaymentService.get_payment_methods(self.request.user)

    def get_serializer_class(self):
        return PaymentMethodSerializer

    @api_error_handler
    @rate_limit(profile="READ_OPERATION", scope="payment_method_list")
    def list(self, request, *args, **kwargs):
        """Get user's payment methods"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        return APIResponse.success(
            message="Payment methods retrieved", data=serializer.data
        )

    @api_error_handler
    @rate_limit(profile="WRITE_OPERATION", scope="payment_method_create")
    def create(self, request, *args, **kwargs):
        """Create payment method"""
        from apps.billing.serializers import PaymentMethodCreateSerializer

        serializer = PaymentMethodCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Use service layer to create payment method
        payment_method = PaymentService.create_payment_method(
            patient=request.user,
            **serializer.validated_data,
        )

        return APIResponse.created(
            message="Payment method created successfully",
            data=PaymentMethodSerializer(payment_method).data,
        )

    @api_error_handler
    @rate_limit(profile="WRITE_OPERATION", scope="payment_method_update")
    def update(self, request, *args, **kwargs):
        """Update payment method"""
        instance = self.get_object()

        # Only allow updating certain fields
        allowed_fields = ["is_default", "is_active"]
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}

        if not update_data:
            return APIResponse.error(
                message="No valid fields to update",
                code="no_valid_fields",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer to update payment method
        payment_method = PaymentService.update_payment_method(
            payment_method=instance,
            **update_data,
        )

        return APIResponse.success(
            message="Payment method updated successfully",
            data=PaymentMethodSerializer(payment_method).data,
        )

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="set-default")
    @rate_limit(profile="WRITE_OPERATION", scope="set_default_payment_method")
    def set_default(self, request, pk=None):
        """Set payment method as default"""
        instance = self.get_object()

        # Use service layer to set default
        payment_method = PaymentService.set_default_payment_method(instance)

        return APIResponse.success(
            message="Payment method set as default",
            data=PaymentMethodSerializer(payment_method).data,
        )


class RefundViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing refunds (admin/staff only)
    """

    permission_classes = [IsAdminOrStaff]
    serializer_class = RefundSerializer

    def get_queryset(self):
        """Get refunds queryset"""
        return Refund.objects.select_related(
            "payment", "bill", "payment__patient", "created_by"
        ).all()

    @api_error_handler
    @rate_limit(profile="READ_OPERATION", scope="refund_list")
    def list(self, request, *args, **kwargs):
        """List refunds"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return APIResponse.from_paginated_response(
                paginator=self.paginator,
                data=serializer.data,
                message="Refunds retrieved successfully",
            )

        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(
            message="Refunds retrieved successfully",
            data=serializer.data,
        )

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="mark-completed")
    @rate_limit(profile="WRITE_OPERATION", scope="mark_refund_completed")
    def mark_completed(self, request, pk=None):
        """Mark refund as completed (admin/staff only)"""
        instance = self.get_object()

        # Use service layer to mark refund as completed
        refund = PaymentService.mark_refund_completed(
            refund=instance,
            user=request.user,
        )

        return APIResponse.success(
            message="Refund marked as completed",
            data=RefundSerializer(refund).data,
        )


class InsuranceClaimViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing insurance claims
    """

    permission_classes = [IsAdminOrStaff]
    serializer_class = InsuranceClaimSerializer

    def get_queryset(self):
        """Get insurance claims queryset"""
        return InsuranceClaim.objects.select_related(
            "bill", "patient", "created_by"
        ).all()

    def get_serializer_class(self):
        """Return appropriate serializer"""
        if self.action == "create":
            return InsuranceClaimCreateSerializer
        return InsuranceClaimSerializer

    @api_error_handler
    @rate_limit(profile="READ_OPERATION", scope="insurance_claim_list")
    def list(self, request, *args, **kwargs):
        """List insurance claims"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return APIResponse.from_paginated_response(
                paginator=self.paginator,
                data=serializer.data,
                message="Insurance claims retrieved successfully",
            )

        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(
            message="Insurance claims retrieved successfully",
            data=serializer.data,
        )

    @api_error_handler
    @rate_limit(profile="WRITE_OPERATION", scope="insurance_claim_create")
    def create(self, request, *args, **kwargs):
        """Create insurance claim"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.billing.services.billing_service import InsuranceClaimService
        from apps.billing.models import Bill

        # Get bill
        try:
            bill = Bill.objects.get(id=serializer.validated_data["bill_id"])
        except Bill.DoesNotExist:
            raise ValidationError("Bill not found")

        # Use service layer to create claim
        claim = InsuranceClaimService.create_claim(
            bill=bill,
            user=request.user,
            **{k: v for k, v in serializer.validated_data.items() if k != "bill_id"},
        )

        return APIResponse.created(
            message="Insurance claim created successfully",
            data=InsuranceClaimSerializer(claim).data,
        )

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="submit")
    @rate_limit(profile="WRITE_OPERATION", scope="submit_insurance_claim")
    def submit(self, request, pk=None):
        """Submit insurance claim to insurance company"""
        instance = self.get_object()

        from apps.billing.services.billing_service import InsuranceClaimService

        # Use service layer to submit claim
        claim = InsuranceClaimService.submit_claim(
            claim=instance,
            user=request.user,
        )

        return APIResponse.success(
            message="Insurance claim submitted successfully",
            data=InsuranceClaimSerializer(claim).data,
        )
