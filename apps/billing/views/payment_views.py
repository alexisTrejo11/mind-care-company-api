from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.core.permissions import IsAdminOrStaff, IsPatient
from apps.core.exceptions.base_exceptions import ValidationError
from apps.core.decorators.error_handler import api_error_handler
from apps.core.decorators.rate_limit import rate_limit
from apps.core.responses.api_response import APIResponse

from apps.billing.services import BillingService, PaymentService, StripeService
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


@extend_schema_view(
    list=extend_schema(summary="List payments with filtering", tags=["Payments"]),
    retrieve=extend_schema(summary="Get payment details", tags=["Payments"]),
    create=extend_schema(
        summary="Create payment (cash/bank/manual)", tags=["Payments", "Admin"]
    ),
    create_online_intent=extend_schema(
        summary="Create Stripe payment intent",
        tags=["Payments", "Online"],
        methods=["post"],
    ),
    confirm_online_payment=extend_schema(
        summary="Confirm Stripe payment", tags=["Payments", "Online"], methods=["post"]
    ),
    verify_bank_transfer=extend_schema(
        summary="Verify bank transfer (staff only)",
        tags=["Payments", "Admin"],
        methods=["post"],
    ),
    process_refund=extend_schema(
        summary="Issue payment refund",
        tags=["Payments", "Refunds", "Admin"],
        methods=["post"],
    ),
    list_refunds=extend_schema(
        summary="List refunds for payment",
        tags=["Payments", "Refunds"],
        methods=["get"],
    ),
)
class PaymentViewSet(viewsets.ModelViewSet):
    """
    Unified ViewSet to handle all payment operations.

    Provides comprehensive payment processing including:
    - Recording and tracking payments (cash, bank transfer, online)
    - Creating Stripe payment intents for online checkout
    - Verifying bank transfer payments
    - Processing and tracking refunds
    - Listing and filtering payment history

    **Access Control:**
    - List/Retrieve: Any authenticated user (filtered by permissions)
    - Create: Patient or Admin/Staff
    - Online Intent: Patient or Admin/Staff
    - Confirm Payment: Patient or Admin/Staff
    - Verify/Refund: Admin/Staff only
    - List Refunds: Any authenticated user

    **Payment Methods Supported:**
    - **cash**: Cash payment (auto-reference generated)
    - **bank_transfer**: Bank transfer (ACH, wire, etc.) - requires verification
    - **online**: Stripe payment via card or digital wallet
    - **digital_wallet**: Apple Pay, Google Pay (via Stripe)

    **Filtering Capabilities:**
    - **Date Range**: start_date, end_date (payment date)
    - **Amount Range**: min_amount, max_amount (payment amount)
    - **Status**: status (pending, completed, failed, refunded)
    - **Method**: payment_method (cash, bank_transfer, online, digital_wallet)
    - **User**: patient_id
    - **Bill**: bill_id
    - **Search**: Full-text search on payment_number, patient name, email, bank reference, notes

    **Ordering Options:**
    - payment_date (default: -payment_date, newest first)
    - amount
    - created_at
    - status

    **Common Use Cases:**
    - GET /api/payments/ - List user's payments
    - GET /api/payments/123/ - View payment details
    - POST /api/payments/ - Record manual payment
    - POST /api/payments/online/intent/ - Create online payment intent
    - POST /api/payments/{id}/online/confirm/{intent_id}/ - Confirm online payment
    - POST /api/payments/123/verify-bank-transfer/ - Verify bank transfer
    - POST /api/payments/123/refunds/ - Issue refund
    - GET /api/payments/123/refunds/ - View payment's refunds

    **Payment Processing Workflows:**

    1. **Cash Payment:**
       - POST to create payment
       - Auto-generates reference number
       - Status: pending → completed (admin confirms)

    2. **Bank Transfer:**
       - POST to create payment
       - Bank reference tracked
       - Status: pending → completed (admin verifies)
       - POST verify-bank-transfer/ to confirm

    3. **Online Payment (Stripe):**
       - POST online/intent/ to create payment intent
       - Returns client_secret for frontend
       - Frontend processes payment with Stripe Elements
       - POST online/confirm/{intent_id}/ to confirm
       - Status: pending → completed (Stripe webhook confirms)

    4. **Refund Processing:**
       - POST {id}/refunds/ to initiate refund
       - Can refund full or partial amount
       - Multiple refunds allowed per payment
       - Stripe refunds processed automatically
       - Cash/bank refunds tracked for manual processing
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
            return [IsPatient(), IsAdminOrStaff()]
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
    ViewSet for managing user's stored payment methods.

    Provides payment method storage and retrieval for customers,
    enabling reusable payment information for future transactions.
    Supports multiple payment methods with default method selection.

    **Access Control:**
    - All operations: Authenticated users (can only manage own methods)
    - List: Get user's payment methods
    - Create: Add new payment method
    - Update: Modify method details (limited fields)
    - Set Default: Mark as default payment method

    **Payment Method Operations:**
    - GET /api/payment-methods/ - List user's payment methods
    - POST /api/payment-methods/ - Add new payment method
    - PATCH /api/payment-methods/{id}/ - Update method (is_active field)
    - POST /api/payment-methods/{id}/set-default/ - Make default
    - DELETE /api/payment-methods/{id}/ - Remove payment method

    **Updatable Fields:**
    - is_default: Set method as default payment method
    - is_active: Activate or deactivate method

    **Payment Method Types:**
    - **card**: Credit/debit card (via Stripe)
    - **bank_transfer**: Bank account for ACH transfers
    - **cash**: Cash payment (manual)
    - **digital_wallet**: Apple Pay, Google Pay (via Stripe)

    **Security Features:**
    - Sensitive data masked (last 4 digits only shown)
    - Card details only visible for card type methods
    - Bank details only visible for bank transfer methods
    - PCI compliance through Stripe tokenization

    **Common Use Cases:**
    - List saved credit cards
    - Add new payment method
    - Set default payment method for future transactions
    - Disable old payment method
    - Manage multiple payment methods per user
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
    ViewSet for managing refunds (admin/staff only).

    Provides refund management and tracking for issued refunds.
    Handles refund processing, status updates, and completion tracking.
    All operations restricted to admin/staff users.

    **Access Control:**
    - All operations: Admin/Staff only
    - Patients can initiate refunds via Payment ViewSet
    - Admin/Staff manages completion and status

    **Refund Operations:**
    - GET /api/refunds/ - List all refunds
    - GET /api/refunds/{id}/ - View refund details
    - POST /api/refunds/{id}/mark-completed/ - Mark refund processed
    - PATCH /api/refunds/{id}/ - Update refund details

    **Refund Status Tracking:**
    - "pending": Refund initiated, awaiting processing
    - "completed": Refund successfully issued
    - "failed": Refund failed (see admin notes)
    - "cancelled": Refund cancelled, no money returned

    **Processing Methods:**
    - **Card**: Automatic Stripe refund (3-5 business days)
    - **Bank Transfer**: Manual reversal instructions
    - **Cash**: Manual refund to customer
    - **Digital Wallet**: Automatic wallet refund

    **Refund Reasons Supported:**
    - patient_request: Customer requested
    - incorrect_charge: Billing error
    - insurance_adjustment: Insurance change
    - service_not_rendered: Service not completed
    - policy_violation: Terms violation
    - payment_reversal: Transaction reversal
    - customer_dissatisfaction: Satisfaction issue
    - other: Other reason

    **Partial & Full Refunds:**
    - Supports partial refund amounts
    - Multiple refunds per payment allowed
    - Total cannot exceed original payment
    - Each tracked separately with audit trail

    **Common Use Cases:**
    - Process customer refund requests
    - Handle returned/cancelled services
    - Correct billing errors
    - Process insurance adjustments
    - Track refund status for customers
    - Generate refund reports

    **Refund Workflow:**
    1. Customer/Staff initiates refund request (via Payment ViewSet)
    2. Refund record created with "pending" status
    3. For cards: Stripe processes automatically
    4. For bank/cash: Admin processes manually
    5. Mark-completed action updates status
    6. Customer notified when complete
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
    ViewSet for managing insurance claims (admin/staff only).

    Provides comprehensive insurance claim management including creation,
    submission, status tracking, and claim lifecycle management. Supports
    complex medical coding (ICD-10 diagnosis, CPT procedures) and EDI
    standards compliance for insurance submissions.

    **Access Control:**
    - All operations: Admin/Staff only
    - Patients view claims via Bill/Payment endpoints
    - Admin/Staff manages full claim lifecycle

    **Claim Operations:**
    - GET /api/insurance-claims/ - List all claims
    - GET /api/insurance-claims/{id}/ - View claim details
    - POST /api/insurance-claims/ - Create new claim
    - PATCH /api/insurance-claims/{id}/ - Update claim
    - POST /api/insurance-claims/{id}/submit/ - Submit to insurer

    **Claim Status Progression:**
    - "draft": Initial claim, not yet submitted
    - "submitted": Sent to insurance company
    - "acknowledged": Insurance received and processing
    - "pending_review": Active review by insurer
    - "approved": Approved for payment
    - "approved_partial": Partially approved
    - "denied": Denied by insurer
    - "paid": Payment received from insurer
    - "appealed": Denial appealed

    **Claim Information:**
    - **Insurance Details**: Company, policy, group number
    - **Subscriber Info**: Policy holder, relationship to patient
    - **Medical Codes**: Diagnosis (ICD-10), Procedure (CPT) codes
    - **Amounts**: Claimed, insurance responsibility, patient responsibility, denied
    - **Dates**: Service date, submission dates, decision dates
    - **EDI Reference**: EDI file, reference number, payer claim number

    **Medical Coding:**
    - **Diagnosis Codes**: ICD-10 format (e.g., "E10.9", "J44.0")
    - **Procedure Codes**: CPT format (e.g., "99213", "92004")
    - Multiple codes supported per claim
    - Automatically validated on submission

    **Amount Breakdown:**
    - total_claimed_amount: Total bill for services
    - insurance_responsibility: Amount insurer pays
    - patient_responsibility: Patient copay/coinsurance
    - denied_amount: Amount insurer denies
    - Formula: insurance + patient + denied = total_claimed_amount

    **Subscriber Relationships:**
    - "self": Patient is policy holder
    - "spouse": Spouse's insurance policy
    - "child": Parent's insurance (child beneficiary)
    - "other": Other coverage arrangement

    **EDI Integration:**
    - Supports X.12 (EDI) electronic submissions
    - Generates EDI files for submission
    - Tracks EDI reference numbers
    - Payer claim numbers for follow-up
    - HIPAA-compliant transmissions

    **Common Use Cases:**
    - Create and submit insurance claims
    - Track claim status and payments
    - Handle claim denials and appeals
    - Generate EOB (Explanation of Benefits) summaries
    - Manage secondary insurance claims
    - Follow up on pending claims
    - Generate claim aging reports

    **Claim Workflow:**
    1. Admin creates claim from bill
    2. Populates insurance and patient responsibility amounts
    3. Adds diagnosis and procedure codes
    4. Submit to insurance company (generates EDI)
    5. Monitor status until payment received
    6. Handle denials with appeals if needed
    7. Reconcile payment with EOB
    8. Update patient responsibility

    **Insurance Company Integration:**
    - Multiple insurance companies supported
    - Tracks coverage details per claim
    - Manages denials and appeals
    - Supports secondary insurance
    - Integrates with claim scrubbing services
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
