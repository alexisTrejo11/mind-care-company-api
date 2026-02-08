from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse

from apps.core.permissions import IsAdminOrStaff, IsSpecialist, IsPatient
from apps.core.exceptions.base_exceptions import ValidationError
from apps.core.decorators.error_handler import api_error_handler
from apps.core.decorators.rate_limit import rate_limit
from apps.core.responses.api_response import APIResponse

from apps.billing.services import BillingService, InvoiceService, PaymentService
from apps.billing.serializers import (
    BillSerializer,
    BillCreateSerializer,
    BillUpdateSerializer,
    BillFilterSerializer,
    BillingStatsSerializer,
    PaymentCreateSerializer,
    BillFilterSerializer,
    PaymentSerializer,
)


class BillViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing bills.

    Filtering is handled by the BillFilter class which supports:
    - start_date, end_date: Filter by invoice date range
    - min_amount, max_amount: Filter by total amount
    - invoice_status: Filter by status
    - patient_id, specialist_id: Filter by user
    - insurance_company, has_insurance: Filter by insurance info
    - search: Full-text search across bill details

    Example: /api/bills/?start_date=2024-01-01&search=john&invoice_status=pending
    """

    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]
    filterset_class = BillFilter
    search_fields = [
        "bill_number",
        "patient__first_name",
        "patient__last_name",
        "patient__email",
        "insurance_company",
        "notes",
    ]

    ordering_fields = [
        "invoice_date",
        "due_date",
        "total_amount",
        "balance_due",
        "created_at",
    ]
    ordering = ["-invoice_date"]

    def get_permissions(self):
        """Assign permissions based on action"""
        if self.action in ["create"]:
            return [IsAdminOrStaff() | IsSpecialist()]
        elif self.action in [
            "update",
            "partial_update",
            "send_invoice",
            "send_reminder",
            "mark_as_paid",
            "cancel",
        ]:
            return [IsAdminOrStaff()]
        elif self.action in ["invoice_pdf"]:
            return [IsAdminOrStaff() | IsSpecialist() | IsPatient()]
        else:
            return [IsAuthenticated()]

    def get_queryset(self):
        """Get filtered queryset based on user permissions"""
        user = self.request.user
        return BillingService.get_bill_queryset(user)

    def get_serializer_class(self):
        """Return the appropriate serializer based on the action"""
        if self.action == "create":
            return BillCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return BillUpdateSerializer
        return BillSerializer

    @api_error_handler
    @rate_limit(profile="READ_OPERATION", scope="bill_list")
    def list(self, request, *args, **kwargs):
        """List bills with advanced filtering"""
        filter_serializer = BillFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return APIResponse.from_paginated_response(
                paginator=self.paginator,
                data=serializer.data,
                message="Bills retrieved successfully",
            )

        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(
            message="Bills retrieved successfully", data=serializer.data
        )

    @api_error_handler
    @rate_limit(profile="READ_OPERATION", scope="bill_detail")
    def retrieve(self, request, *args, **kwargs):
        """Get bill details with permissions check"""
        instance = self.get_object()

        # Check if user has permission to view this specific bill
        if not BillingService.can_view_bill(request.user, instance):
            raise PermissionDenied("You do not have permission to view this bill")

        serializer = self.get_serializer(instance)
        return APIResponse.success(
            message="Bill details retrieved", data=serializer.data
        )

    @api_error_handler
    @rate_limit(profile="WRITE_OPERATION", scope="bill_create")
    def create(self, request, *args, **kwargs):
        """Create new bill from appointment"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        bill = BillingService.create_bill_from_appointment(
            appointment_id=serializer.validated_data["appointment_id"],
            created_by=request.user,
            **serializer.validated_data,
        )

        return APIResponse.created(
            message="Bill created successfully",
            data=BillSerializer(bill).data,
        )

    @api_error_handler
    @rate_limit(profile="WRITE_OPERATION", scope="bill_update")
    def update(self, request, *args, **kwargs):
        """Update bill"""
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Use service layer to update bill
        bill = BillingService.update_bill(
            bill=instance,
            user=request.user,
            **serializer.validated_data,
        )

        return APIResponse.success(
            message="Bill updated successfully",
            data=BillSerializer(bill).data,
        )

    @api_error_handler
    @action(detail=True, methods=["get"], url_path="invoice-pdf")
    @rate_limit(profile="READ_OPERATION", scope="invoice_pdf")
    def invoice_pdf(self, request, pk=None):
        """Generate invoice PDF"""
        instance = self.get_object()

        # Check permissions
        if not BillingService.can_view_bill(request.user, instance):
            raise PermissionDenied("You do not have permission to view this invoice")

        pdf_content = InvoiceService.generate_invoice_pdf(instance)

        response = HttpResponse(pdf_content, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="invoice-{instance.bill_number}.pdf"'
        )

        return response

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="send-invoice")
    @rate_limit(profile="WRITE_OPERATION", scope="send_invoice")
    def send_invoice(self, request, pk=None):
        """Send invoice email to patient"""
        instance = self.get_object()

        # Check permissions (admin/staff or specialist for this appointment)
        if request.user.user_type == "specialist":
            if (
                not hasattr(request.user, "specialist_profile")
                or instance.appointment.specialist != request.user.specialist_profile
            ):
                raise PermissionDenied(
                    "You can only send invoices for your own appointments"
                )

        elif request.user.user_type not in ["admin", "staff"]:
            raise PermissionDenied(
                "Only admins, staff, or specialists can send invoices"
            )

        result = InvoiceService.send_invoice_email(instance)
        return APIResponse.success(message="Invoice sent successfully", data=result)

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="send-reminder")
    @rate_limit(profile="WRITE_OPERATION", scope="send_reminder")
    def send_reminder(self, request, pk=None):
        """Send payment reminder"""
        instance = self.get_object()

        # Check if bill is ongoing
        if not BillingService.is_bill_ongoing(instance):
            raise ValidationError("Cannot send reminder for a bill that is not ongoing")

        # Use service layer to send reminder
        result = BillingService.send_payment_reminder(instance)

        return APIResponse.success(
            message="Payment reminder sent successfully",
            data=result,
        )

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="mark-as-paid")
    @rate_limit(profile="WRITE_OPERATION", scope="mark_paid")
    def mark_as_paid(self, request, pk=None):
        """Mark bill as paid manually (for admin/staff)"""
        instance = self.get_object()

        notes = request.data.get("notes", "")

        # Use service layer to mark bill as paid
        bill = BillingService.mark_bill_as_paid(
            bill=instance,
            user=request.user,
            notes=notes,
        )

        return APIResponse.success(
            message="Bill marked as paid",
            data=BillSerializer(bill).data,
        )

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="cancel")
    @rate_limit(profile="WRITE_OPERATION", scope="cancel_bill")
    def cancel(self, request, pk=None):
        """Cancel bill (admin/staff only)"""
        instance = self.get_object()

        reason = request.data.get("reason", "")

        # Use service layer to cancel bill
        bill = BillingService.cancel_bill(
            bill=instance,
            user=request.user,
            reason=reason,
        )

        return APIResponse.success(
            message="Bill cancelled successfully",
            data=BillSerializer(bill).data,
        )

    @api_error_handler
    @action(detail=False, methods=["get"], url_path="overdue")
    @rate_limit(profile="READ_OPERATION", scope="overdue_bills")
    def overdue_bills(self, request):
        """Get overdue bills (admin/staff only)"""
        queryset = self.get_queryset()
        overdue_bills = BillingService.get_overdue_bills(queryset)

        # Limit results
        page = self.paginate_queryset(overdue_bills)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return APIResponse.from_paginated_response(
                paginator=self.paginator,
                data=serializer.data,
                message="Overdue bills retrieved",
            )

        serializer = self.get_serializer(overdue_bills[:50], many=True)
        return APIResponse.success(
            message="Overdue bills retrieved", data=serializer.data
        )

    @api_error_handler
    @action(detail=False, methods=["get"], url_path="my-bills")
    @rate_limit(profile="READ_OPERATION", scope="my_bills")
    def my_bills(self, request):
        """Get current user's bills"""
        summary = BillingService.get_user_billing_summary(request.user)

        recent_bills = summary.pop("recent_bills")
        serializer = self.get_serializer(recent_bills, many=True)

        summary["recent_bills"] = serializer.data
        return APIResponse.success(message="Your billing information", data=summary)

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="payments/cash")
    @rate_limit(profile="WRITE_OPERATION", scope="cash_payment")
    def create_cash_payment(self, request, pk=None):
        """Create cash payment for bill"""
        instance = self.get_object()

        # Check permissions
        if request.user.user_type not in ["admin", "staff"]:
            if request.user.user_type == "patient" and instance.patient != request.user:
                raise PermissionDenied("You can only make payments for your own bills")
            elif request.user.user_type == "specialist":
                raise PermissionDenied("Specialists cannot make payments")

        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create cash payment
        payment = PaymentService.create_cash_payment(
            bill_id=instance.id,
            amount=serializer.validated_data["amount"],
            created_by=request.user,
            notes=serializer.validated_data.get("notes", ""),
        )

        return APIResponse.created(
            message="Cash payment created successfully",
            data=PaymentSerializer(payment).data,
        )

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="payments/bank-transfer")
    @rate_limit(profile="WRITE_OPERATION", scope="bank_transfer_payment")
    def create_bank_transfer_payment(self, request, pk=None):
        """Create bank transfer payment for bill"""
        instance = self.get_object()

        # Check permissions
        if request.user.user_type not in ["admin", "staff"]:
            if request.user.user_type == "patient" and instance.patient != request.user:
                raise PermissionDenied("You can only make payments for your own bills")
            elif request.user.user_type == "specialist":
                raise PermissionDenied("Specialists cannot make payments")

        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Validate bank transfer specific fields
        if not serializer.validated_data.get("bank_reference"):
            raise ValidationError("Bank reference is required for bank transfers")
        if not serializer.validated_data.get("bank_name"):
            raise ValidationError("Bank name is required for bank transfers")

        # Create bank transfer payment
        payment = PaymentService.create_bank_transfer_payment(
            bill_id=instance.id,
            amount=serializer.validated_data["amount"],
            bank_reference=serializer.validated_data["bank_reference"],
            bank_name=serializer.validated_data["bank_name"],
            created_by=request.user,
            notes=serializer.validated_data.get("notes", ""),
        )

        return APIResponse.created(
            message="Bank transfer payment created successfully",
            data=PaymentSerializer(payment).data,
        )


class BillingStatsViewSet(viewsets.ListAPIView):
    """
    ViewSet for billing statistics
    """

    permission_classes = [IsAdminOrStaff | IsSpecialist]

    @api_error_handler
    @rate_limit(profile="READ_OPERATION", scope="billing_stats")
    def list(self, request):
        """Get billing statistics"""
        stats_serializer = BillingStatsSerializer(data=request.query_params)
        stats_serializer.is_valid(raise_exception=True)

        # If specialist, only show their stats. Admin/staff can filter by specialist_id or see all.
        specialist_id = None
        if request.user.user_type == "specialist":
            if hasattr(request.user, "specialist_profile"):
                specialist_id = request.user.specialist_profile.id

        if request.user.user_type in ["admin", "staff"]:
            specialist_id = request.query_params.get("specialist_id", specialist_id)

        stats = BillingService.get_billing_statistics(
            period=stats_serializer.validated_data["period"],
            specialist_id=specialist_id,
        )

        return APIResponse.success(message="Billing statistics retrieved", data=stats)
