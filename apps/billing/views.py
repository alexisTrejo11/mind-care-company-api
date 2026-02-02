from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from core.decorators.error_handler import api_error_handler
from core.responses.api_response import APIResponse

from .models import Bill, Payment, Refund, InsuranceClaim, PaymentMethod
from .serializers import (
    BillSerializer,
    BillCreateSerializer,
    BillUpdateSerializer,
    BillFilterSerializer,
    PaymentSerializer,
    PaymentCreateSerializer,
    RefundSerializer,
    InsuranceClaimSerializer,
    PaymentMethodSerializer,
    CreatePaymentIntentSerializer,
    BillingStatsSerializer,
)
from .services import (
    BillingService,
    StripeService,
    InvoiceService,
)
from apps.notifications.services import NotificationService
from apps.notifications.tasks import send_notification


class BillListView(APIView):
    """
    GET /api/bills/
    List and search bills with filters
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def get(self, request):
        """List bills with filters"""
        # Validate filter parameters
        filter_serializer = BillFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)

        filters = filter_serializer.validated_data
        page = filters.pop("page", 1)
        page_size = filters.pop("page_size", 20)

        # Apply role-based filtering
        queryset = Bill.objects.select_related(
            "patient",
            "appointment",
            "appointment__specialist",
            "appointment__specialist__user",
        )

        if request.user.user_type == "patient":
            queryset = queryset.filter(patient=request.user)
        elif request.user.user_type == "specialist":
            if hasattr(request.user, "specialist_profile"):
                queryset = queryset.filter(
                    appointment__specialist=request.user.specialist_profile
                )

        # Apply filters
        if patient_id := filters.get("patient_id"):
            queryset = queryset.filter(patient__user_id=patient_id)

        if specialist_id := filters.get("specialist_id"):
            queryset = queryset.filter(appointment__specialist_id=specialist_id)

        if payment_status := filters.get("payment_status"):
            queryset = queryset.filter(payment_status=payment_status)

        if invoice_status := filters.get("invoice_status"):
            queryset = queryset.filter(invoice_status=invoice_status)

        # Date range filtering
        if start_date := filters.get("start_date"):
            queryset = queryset.filter(invoice_date__gte=start_date)

        if end_date := filters.get("end_date"):
            queryset = queryset.filter(invoice_date__lte=end_date)

        # Amount filtering
        if min_amount := filters.get("min_amount"):
            queryset = queryset.filter(total_amount__gte=min_amount)

        if max_amount := filters.get("max_amount"):
            queryset = queryset.filter(total_amount__lte=max_amount)

        # Insurance filtering
        if has_insurance := filters.get("has_insurance"):
            if has_insurance:
                queryset = queryset.filter(insurance_company__isnull=False)
            else:
                queryset = queryset.filter(insurance_company__isnull=True)

        # Search
        if search_query := filters.get("search"):
            queryset = queryset.filter(
                Q(bill_number__icontains=search_query)
                | Q(patient__first_name__icontains=search_query)
                | Q(patient__last_name__icontains=search_query)
                | Q(insurance_company__icontains=search_query)
                | Q(policy_number__icontains=search_query)
            )

        # Ordering
        ordering = filters.get("ordering", "-invoice_date")
        queryset = queryset.order_by(ordering)

        # Pagination
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size

        bills = queryset[start:end]

        # Serialize
        serializer = BillSerializer(bills, many=True, context={"request": request})

        # Pagination metadata
        pagination = {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "has_next": end < total,
            "has_previous": page > 1,
        }

        return APIResponse.success(
            message="Bills retrieved successfully",
            data=serializer.data,
            pagination=pagination,
        )


class BillCreateView(APIView):
    """
    POST /api/bills/create/
    Create a new bill from appointment
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_admin_or_staff, user_is_specialist])
    def post(self, request):
        """Create bill"""
        serializer = BillCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        # Create bill using service
        bill = BillingService.create_bill_from_appointment(
            appointment_id=serializer.validated_data["appointment_id"],
            created_by=request.user,
            **serializer.validated_data,
        )

        # Send notification to patient
        send_notification.delay(
            template_name="invoice_created",
            user_id=str(bill.patient.user_id),
            context={
                "bill_number": bill.bill_number,
                "total_amount": float(bill.total_amount),
                "due_date": bill.due_date.isoformat(),
                "payment_url": bill.get_payment_url(),
            },
        )

        return APIResponse.created(
            message="Bill created successfully",
            data=BillSerializer(bill, context={"request": request}).data,
        )


class BillDetailView(APIView):
    """
    GET /api/bills/<bill_number>/
    Get bill details
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def get(self, request, bill_number):
        """Get bill details"""
        try:
            bill = Bill.objects.select_related(
                "patient",
                "appointment",
                "appointment__specialist",
                "appointment__specialist__user",
            ).get(bill_number=bill_number)

            # Check permissions
            if request.user.user_type == "patient":
                if bill.patient != request.user:
                    raise PermissionError("Cannot view another patient's bill")
            elif request.user.user_type == "specialist":
                if not hasattr(request.user, "specialist_profile"):
                    raise PermissionError("User is not a specialist")
                if bill.appointment.specialist != request.user.specialist_profile:
                    raise PermissionError(
                        "Cannot view bill for another specialist's appointment"
                    )

            serializer = BillSerializer(bill, context={"request": request})

            return APIResponse.success(
                message="Bill details retrieved", data=serializer.data
            )

        except Bill.DoesNotExist:
            return APIResponse.error(
                message="Bill not found", code="bill_not_found", status_code=404
            )


class BillUpdateView(APIView):
    """
    PATCH /api/bills/<bill_number>/update/
    Update bill information
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_admin_or_staff])
    def patch(self, request, bill_number):
        """Update bill"""
        try:
            bill = Bill.objects.get(bill_number=bill_number)

            serializer = BillUpdateSerializer(
                bill, data=request.data, partial=True, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)

            serializer.save()

            return APIResponse.success(
                message="Bill updated successfully", data=serializer.data
            )

        except Bill.DoesNotExist:
            return APIResponse.error(
                message="Bill not found", code="bill_not_found", status_code=404
            )


class PaymentCreateView(APIView):
    """
    POST /api/payments/create/
    Create a payment for a bill
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_patient, user_is_admin_or_staff])
    def post(self, request):
        """Create payment"""
        serializer = PaymentCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        # For patients, ensure they're paying their own bill
        if request.user.user_type == "patient":
            bill_id = serializer.validated_data["bill_id"]
            bill = Bill.objects.get(id=bill_id)

            if bill.patient != request.user:
                raise PermissionError("Cannot make payment for another patient's bill")

        # Create payment using service
        payment = BillingService.create_payment(
            bill_id=serializer.validated_data["bill_id"],
            amount=serializer.validated_data["amount"],
            payment_method=serializer.validated_data["payment_method"],
            patient=request.user if request.user.user_type == "patient" else None,
            created_by=request.user,
            **serializer.validated_data,
        )

        serializer = PaymentSerializer(payment, context={"request": request})

        return APIResponse.created(
            message="Payment created successfully", data=serializer.data
        )


class CreatePaymentIntentView(APIView):
    """
    POST /api/payments/create-intent/
    Create Stripe Payment Intent for online payment
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_patient, user_is_admin_or_staff])
    def post(self, request):
        """Create Stripe Payment Intent"""
        serializer = CreatePaymentIntentSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        bill = serializer.validated_data["bill"]
        amount = serializer.validated_data["amount"]

        # For patients, ensure they're paying their own bill
        if request.user.user_type == "patient" and bill.patient != request.user:
            raise PermissionError("Cannot make payment for another patient's bill")

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


class ConfirmPaymentView(APIView):
    """
    POST /api/payments/<payment_intent_id>/confirm/
    Confirm Stripe Payment Intent
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def post(self, request, payment_intent_id):
        """Confirm payment intent"""
        result = StripeService.confirm_payment_intent(payment_intent_id)

        if result["status"] == "succeeded":
            # Send payment confirmation notification
            send_notification.delay(
                template_name="payment_received",
                user_id=str(request.user.user_id),
                context={
                    "payment_amount": result.get("amount", 0),
                    "bill_number": result.get("bill_number", ""),
                    "payment_date": timezone.now().isoformat(),
                },
            )

            return APIResponse.success(
                message="Payment confirmed successfully", data=result
            )
        else:
            return APIResponse.error(
                message=f'Payment confirmation failed: {result.get("status")}',
                code="payment_confirmation_failed",
                data=result,
            )


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """
    POST /api/webhooks/stripe/
    Handle Stripe webhook events
    """

    permission_classes = [AllowAny]

    @method_decorator(csrf_exempt)
    def post(self, request):
        """Handle Stripe webhook"""
        import json

        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        try:
            result = StripeService.handle_webhook(payload, sig_header)

            return APIResponse.success(
                message="Webhook processed successfully", data=result
            )

        except Exception as e:
            logger.error(f"Error processing Stripe webhook: {str(e)}", exc_info=True)

            return APIResponse.error(
                message="Failed to process webhook",
                code="webhook_error",
                status_code=400,
            )


class InvoicePDFView(APIView):
    """
    GET /api/bills/<bill_number>/invoice/
    Generate and download invoice PDF
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def get(self, request, bill_number):
        """Generate invoice PDF"""
        try:
            bill = Bill.objects.get(bill_number=bill_number)

            # Check permissions
            if request.user.user_type == "patient":
                if bill.patient != request.user:
                    raise PermissionError("Cannot access another patient's invoice")
            elif request.user.user_type == "specialist":
                if not hasattr(request.user, "specialist_profile"):
                    raise PermissionError("User is not a specialist")
                if bill.appointment.specialist != request.user.specialist_profile:
                    raise PermissionError(
                        "Cannot access invoice for another specialist's appointment"
                    )

            # Generate PDF
            pdf_content = InvoiceService.generate_invoice_pdf(bill)

            # Create response
            response = HttpResponse(pdf_content, content_type="application/pdf")
            response["Content-Disposition"] = (
                f'attachment; filename="invoice-{bill.bill_number}.pdf"'
            )

            return response

        except Bill.DoesNotExist:
            return APIResponse.error(
                message="Bill not found", code="bill_not_found", status_code=404
            )


class BillingStatsView(APIView):
    """
    GET /api/billing/stats/
    Get billing statistics
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_admin_or_staff, user_is_specialist])
    def get(self, request):
        """Get billing statistics"""
        stats_serializer = BillingStatsSerializer(data=request.query_params)
        stats_serializer.is_valid(raise_exception=True)

        # For specialists, only show their own stats
        specialist_id = None
        if request.user.user_type == "specialist":
            if hasattr(request.user, "specialist_profile"):
                specialist_id = request.user.specialist_profile.id

        # Allow filtering by specialist for admins
        if request.user.user_type in ["admin", "staff"]:
            specialist_id = request.query_params.get("specialist_id", specialist_id)

        # Get statistics using service
        stats = BillingService.get_billing_statistics(
            period=stats_serializer.validated_data["period"],
            specialist_id=specialist_id,
        )

        return APIResponse.success(message="Billing statistics retrieved", data=stats)


class MyBillsView(APIView):
    """
    GET /api/bills/me/
    Get current user's bills
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def get(self, request):
        """Get user's bills"""
        # For patients, show their bills
        # For specialists, show bills for their appointments
        # For admins/staff, show recent bills

        if request.user.user_type == "patient":
            queryset = Bill.objects.filter(patient=request.user)
        elif request.user.user_type == "specialist":
            if hasattr(request.user, "specialist_profile"):
                queryset = Bill.objects.filter(
                    appointment__specialist=request.user.specialist_profile
                )
            else:
                queryset = Bill.objects.none()
        else:
            # Admin/staff: show recent bills
            queryset = Bill.objects.all().order_by("-created_at")[:20]

        # Filter by status if provided
        status = request.query_params.get("status")
        if status:
            queryset = queryset.filter(payment_status=status)

        # Get overdue bills
        overdue = queryset.filter(
            payment_status="overdue", due_date__lt=timezone.now().date()
        ).count()

        # Get pending bills
        pending = queryset.filter(payment_status__in=["pending", "partial"]).count()

        # Get total balance due
        total_balance = (
            queryset.filter(
                payment_status__in=["pending", "partial", "overdue"]
            ).aggregate(total=Sum("balance_due"))["total"]
            or 0
        )

        # Get recent bills
        recent_bills = queryset.order_by("-created_at")[:10]

        serializer = BillSerializer(
            recent_bills, many=True, context={"request": request}
        )

        return APIResponse.success(
            message="Your billing information",
            data={
                "overdue_count": overdue,
                "pending_count": pending,
                "total_balance_due": float(total_balance),
                "recent_bills": serializer.data,
            },
        )


class PaymentMethodsView(APIView):
    """
    GET/POST /api/payment-methods/
    Manage payment methods
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def get(self, request):
        """Get user's payment methods"""
        payment_methods = PaymentMethod.objects.filter(
            patient=request.user, is_active=True
        ).order_by("-is_default", "-created_at")

        serializer = PaymentMethodSerializer(payment_methods, many=True)

        return APIResponse.success(
            message="Payment methods retrieved", data=serializer.data
        )

    @api_error_handler
    def post(self, request):
        """Add payment method via Stripe"""
        # This would integrate with Stripe Elements or Payment Element
        # For now, return instructions

        from django.conf import settings

        return APIResponse.success(
            message="To add a payment method, use Stripe Elements on the frontend",
            data={
                "stripe_public_key": settings.STRIPE_PUBLISHABLE_KEY,
                "setup_intent_url": "/api/payments/create-setup-intent/",
            },
        )


class OverdueBillsView(APIView):
    """
    GET /api/bills/overdue/
    Get overdue bills
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_admin_or_staff])
    def get(self, request):
        """Get overdue bills"""
        overdue_bills = Bill.objects.filter(
            payment_status="overdue", due_date__lt=timezone.now().date()
        ).select_related(
            "patient",
            "appointment",
            "appointment__specialist",
            "appointment__specialist__user",
        )

        # Filter by specialist if provided
        specialist_id = request.query_params.get("specialist_id")
        if specialist_id:
            overdue_bills = overdue_bills.filter(
                appointment__specialist_id=specialist_id
            )

        # Sort by days overdue
        overdue_bills = sorted(
            overdue_bills,
            key=lambda b: (timezone.now().date() - b.due_date).days,
            reverse=True,
        )

        serializer = BillSerializer(
            overdue_bills[:50], many=True, context={"request": request}
        )

        return APIResponse.success(
            message="Overdue bills retrieved", data=serializer.data
        )


class SendPaymentReminderView(APIView):
    """
    POST /api/bills/<bill_number>/send-reminder/
    Send payment reminder
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    @require_permissions([user_is_admin_or_staff])
    def post(self, request, bill_number):
        """Send payment reminder"""
        try:
            bill = Bill.objects.get(bill_number=bill_number)

            # Check if reminder should be sent
            if bill.payment_status in ["paid", "cancelled", "refunded"]:
                return APIResponse.error(
                    message=f"Cannot send reminder for bill with status: {bill.payment_status}",
                    code="invalid_bill_status",
                )

            # Send notification
            send_notification.delay(
                template_name="payment_reminder",
                user_id=str(bill.patient.user_id),
                context={
                    "bill_number": bill.bill_number,
                    "total_amount": float(bill.total_amount),
                    "balance_due": float(bill.balance_due),
                    "due_date": bill.due_date.isoformat(),
                    "days_overdue": (
                        (timezone.now().date() - bill.due_date).days
                        if bill.payment_status == "overdue"
                        else 0
                    ),
                    "payment_url": bill.get_payment_url(),
                },
            )

            return APIResponse.success(
                message="Payment reminder sent successfully",
                data={
                    "bill_number": bill.bill_number,
                    "patient_email": bill.patient.email,
                    "patient_name": bill.patient.get_full_name(),
                },
            )

        except Bill.DoesNotExist:
            return APIResponse.error(
                message="Bill not found", code="bill_not_found", status_code=404
            )
