from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse

from apps.core.permissions import IsAdminOrStaff, IsSpecialist
from core.decorators.error_handler import api_error_handler
from core.decorators.rate_limit import rate_limit
from core.responses.api_response import APIResponse
from ..models import Bill
from ..serializers import (
    BillSerializer,
    BillCreateSerializer,
    BillUpdateSerializer,
    BillFilterSerializer,
    BillingStatsSerializer,
)
from ..services import BillingService, StripeService, InvoiceService
from apps.core.exceptions.base_exceptions import NotFoundError, ValidationError


class BillViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing bills
    """

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = {
        "payment_status": ["exact"],
        "invoice_status": ["exact"],
        "patient__id": ["exact"],
        "appointment__specialist__id": ["exact"],
        "insurance_company": ["exact", "icontains"],
    }
    search_fields = [
        "bill_number",
        "patient__first_name",
        "patient__last_name",
        "patient__email",
        "insurance_company",
        "policy_number",
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
            return [IsAdminOrStaff, IsSpecialist]
        elif self.action in [
            "update",
            "partial_update",
            "send_invoice",
            "send_reminder",
        ]:
            return [IsAdminOrStaff]
        else:
            return [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Bill.objects.select_related(
            "patient",
            "appointment",
            "appointment__specialist",
            "appointment__specialist__user",
        ).all()

        if user.user_type == "patient":
            queryset = queryset.filter(patient=user)
        elif user.user_type == "specialist":
            if hasattr(user, "specialist_profile"):
                queryset = queryset.filter(
                    appointment__specialist=user.specialist_profile
                )

        # Apply additional filters from query params
        params = self.request.query_params

        # Date range filtering
        start_date = params.get("start_date")
        if start_date:
            queryset = queryset.filter(invoice_date__gte=start_date)

        end_date = params.get("end_date")
        if end_date:
            queryset = queryset.filter(invoice_date__lte=end_date)

        # Amount filtering
        min_amount = params.get("min_amount")
        if min_amount:
            queryset = queryset.filter(total_amount__gte=min_amount)

        max_amount = params.get("max_amount")
        if max_amount:
            queryset = queryset.filter(total_amount__lte=max_amount)

        # Insurance filtering
        has_insurance = params.get("has_insurance")
        if has_insurance:
            if has_insurance.lower() == "true":
                queryset = queryset.filter(insurance_company__isnull=False)
            elif has_insurance.lower() == "false":
                queryset = queryset.filter(insurance_company__isnull=True)

        return queryset

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
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(
            message="Bills retrieved successfully", data=serializer.data
        )

    @api_error_handler
    @rate_limit(profile="READ_OPERATION", scope="bill_detail")
    def retrieve(self, request, *args, **kwargs):
        """Get bill details. If patient, only will see their own bills."""
        instance = self.get_object()

        serializer = self.get_serializer(instance)
        return APIResponse.success(
            message="Bill details retrieved", data=serializer.data
        )

    @api_error_handler
    @rate_limit(profile="WRITE_OPERATION", scope="bill_create")
    def create(self, request, *args, **kwargs):
        """Create new bill"""
        # Check permissions
        if request.user.user_type not in ["admin", "staff", "specialist"]:
            raise PermissionDenied("Only admin, staff, or specialists can create bills")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Use service for business logic
        bill = BillingService.create_bill_from_appointment(
            appointment_id=serializer.validated_data["appointment"],
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

        serializer.save()

        return APIResponse.success(
            message="Bill updated successfully",
            data=serializer.data,
        )

    @api_error_handler
    @action(detail=True, methods=["get"], url_path="invoice-pdf")
    def invoice_pdf(self, request, pk=None):
        """Generate invoice PDF"""
        instance = self.get_object()

        user = request.user
        assert_specialist_in_appointment(user, instance.appointment)

        pdf_content = InvoiceService.generate_invoice_pdf(instance)

        response = HttpResponse(pdf_content, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="invoice-{instance.bill_number}.pdf"'
        )

        return response

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="send-invoice")
    def send_invoice(self, request, pk=None):
        """Send invoice email to patient"""
        instance = self.get_object()

        user = request.user
        assert_specialist_in_appointment(user, instance.appointment)

        result = InvoiceService.send_invoice_email(instance)
        return APIResponse.success(message="Invoice sent successfully", data=result)

    @api_error_handler
    @action(detail=True, methods=["post"], url_path="send-reminder")
    def send_reminder(self, request, pk=None):
        """Send payment reminder"""
        instance = self.get_object()

        if request.user.user_type not in ["admin", "staff"]:
            raise PermissionDenied("Only admin or staff can send payment reminders")

        if instance.payment_status in ["paid", "cancelled", "refunded"]:
            raise ValidationError(
                detail=f"Cannot send reminder for bill with status: {instance.payment_status}"
            )

        # Send notification (placeholder)
        # send_notification.delay(...)

        return APIResponse.success(
            message="Payment reminder sent successfully",
            data={
                "bill_number": instance.bill_number,
                "patient_email": instance.patient.email,
            },
        )

    @api_error_handler
    @action(detail=False, methods=["get"], url_path="overdue")
    def overdue_bills(self, request):
        """Get overdue bills"""
        # Check permissions
        if request.user.user_type not in ["admin", "staff"]:
            raise PermissionDenied("Only admin or staff can view overdue bills")

        from django.utils import timezone

        queryset = self.get_queryset().filter(
            payment_status="overdue", due_date__lt=timezone.now().date()
        )

        # Sort by days overdue
        overdue_bills = sorted(
            queryset,
            key=lambda b: (timezone.now().date() - b.due_date).days,
            reverse=True,
        )

        serializer = self.get_serializer(overdue_bills[:50], many=True)

        return APIResponse.success(
            message="Overdue bills retrieved", data=serializer.data
        )

    @api_error_handler
    @action(detail=False, methods=["get"], url_path="my-bills")
    def my_bills(self, request):
        """Get current user's bills"""
        # Use billing service for summary
        summary = BillingService.get_user_billing_summary(request.user)

        # Get recent bills
        recent_bills = summary.pop("recent_bills")
        serializer = self.get_serializer(recent_bills, many=True)

        summary["recent_bills"] = serializer.data

        return APIResponse.success(message="Your billing information", data=summary)


class BillingStatsViewSet(viewsets.ViewSet):
    """
    ViewSet for billing statistics
    """

    permission_classes = [IsAuthenticated]

    @api_error_handler
    def list(self, request):
        """Get billing statistics"""
        # Check permissions
        if request.user.user_type not in ["admin", "staff", "specialist"]:
            raise PermissionDenied(
                "Only admin, staff, or specialists can view billing statistics"
            )

        # Validate parameters
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


def assert_specialist_in_appointment(user, appointment):
    """Check if the user is the specialist for the given appointment"""

    user = user
    if user.is_specialist():
        if not appointment.is_from_specialist(user.specialist_profile):
            raise PermissionDenied("You do not have permission to send this invoice")
