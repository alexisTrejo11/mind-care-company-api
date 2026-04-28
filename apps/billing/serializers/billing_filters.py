from rest_framework import serializers
from datetime import datetime, date
from decimal import Decimal


class BillFilterSerializer(serializers.Serializer):
    """Serializer for filtering bills"""

    # Date filters
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    due_date_start = serializers.DateField(required=False)
    due_date_end = serializers.DateField(required=False)

    # Amount filters
    min_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"), required=False
    )
    max_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"), required=False
    )

    # Status filters
    invoice_status = serializers.CharField(required=False, max_length=20)
    has_insurance = serializers.BooleanField(required=False)

    # User filters
    patient_id = serializers.IntegerField(required=False)
    specialist_id = serializers.IntegerField(required=False)

    # Search
    search = serializers.CharField(required=False, max_length=100)

    # Pagination/ordering
    ordering = serializers.CharField(required=False, max_length=50)
    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=100)

    def validate_start_date(self, value: date) -> date:
        """Validate start date"""
        if value > datetime.now().date():
            raise serializers.ValidationError("Start date cannot be in the future")
        return value

    def validate_end_date(self, value: date) -> date:
        """Validate end date"""
        if value > datetime.now().date():
            raise serializers.ValidationError("End date cannot be in the future")
        return value

    def validate(self, data: dict) -> dict:
        """Validate filter combinations"""
        # Validate date ranges
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError(
                {"start_date": "Start date must be before or equal to end date"}
            )

        # Validate amount ranges
        min_amount = data.get("min_amount")
        max_amount = data.get("max_amount")

        if min_amount and max_amount and min_amount > max_amount:
            raise serializers.ValidationError(
                {
                    "min_amount": "Minimum amount must be less than or equal to maximum amount"
                }
            )

        # Validate due date ranges
        due_date_start = data.get("due_date_start")
        due_date_end = data.get("due_date_end")

        if due_date_start and due_date_end and due_date_start > due_date_end:
            raise serializers.ValidationError(
                {
                    "due_date_start": "Due date start must be before or equal to due date end"
                }
            )

        return data


class PaymentFilterSerializer(serializers.Serializer):
    """Serializer for filtering payments"""

    # Date filters
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)

    # Payment filters
    payment_method = serializers.CharField(required=False, max_length=20)
    status = serializers.CharField(required=False, max_length=20)

    # Amount filters
    min_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"), required=False
    )
    max_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"), required=False
    )

    # User filters
    patient_id = serializers.IntegerField(required=False)
    bill_id = serializers.IntegerField(required=False)

    # Search
    search = serializers.CharField(required=False, max_length=100)

    # Pagination/ordering
    ordering = serializers.CharField(required=False, max_length=50)
    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=100)

    def validate(self, data: dict) -> dict:
        """Validate filter combinations"""
        # Validate date ranges
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError(
                {"start_date": "Start date must be before or equal to end date"}
            )

        # Validate amount ranges
        min_amount = data.get("min_amount")
        max_amount = data.get("max_amount")

        if min_amount and max_amount and min_amount > max_amount:
            raise serializers.ValidationError(
                {
                    "min_amount": "Minimum amount must be less than or equal to maximum amount"
                }
            )

        return data


class BillingStatsSerializer(serializers.Serializer):
    """Serializer for billing statistics parameters"""

    period = serializers.ChoiceField(
        choices=["today", "week", "month", "year", "all_time"], default="month"
    )
    specialist_id = serializers.IntegerField(required=False)


from rest_framework import serializers
from datetime import datetime, date
from decimal import Decimal
import django_filters
from django.db.models import Q

from apps.billing.models import Bill, Payment


class BillFilterSet(django_filters.FilterSet):
    """FilterSet for Bill filtering"""

    # Date range filters
    start_date = django_filters.DateFilter(
        field_name="invoice_date", lookup_expr="gte", label="Start Date"
    )
    end_date = django_filters.DateFilter(
        field_name="invoice_date", lookup_expr="lte", label="End Date"
    )

    due_date_start = django_filters.DateFilter(
        field_name="due_date", lookup_expr="gte", label="Due Date Start"
    )
    due_date_end = django_filters.DateFilter(
        field_name="due_date", lookup_expr="lte", label="Due Date End"
    )

    # Amount filters
    min_amount = django_filters.NumberFilter(
        field_name="total_amount", lookup_expr="gte", label="Minimum Amount"
    )
    max_amount = django_filters.NumberFilter(
        field_name="total_amount", lookup_expr="lte", label="Maximum Amount"
    )

    # Status filters
    invoice_status = django_filters.ChoiceFilter(
        field_name="invoice_status",
        choices=Bill.INVOICE_STATUS_CHOICES,
        label="Invoice Status",
    )
    has_insurance = django_filters.BooleanFilter(
        field_name="insurance_company",
        method="filter_has_insurance",
        label="Has Insurance",
    )

    # User filters
    patient_id = django_filters.NumberFilter(
        field_name="patient_id", label="Patient ID"
    )

    # Search filter using method
    search = django_filters.CharFilter(
        method="filter_search", label="Search (bill number, patient, insurance, notes)"
    )

    class Meta:
        model = Bill
        fields = [
            "start_date",
            "end_date",
            "due_date_start",
            "due_date_end",
            "min_amount",
            "max_amount",
            "invoice_status",
            "has_insurance",
            "patient_id",
            "search",
        ]

    def filter_has_insurance(self, queryset, name, value):
        """Filter bills by whether they have insurance"""
        if value:
            return queryset.exclude(insurance_company__isnull=True).exclude(
                insurance_company=""
            )
        return queryset.filter(
            Q(insurance_company__isnull=True) | Q(insurance_company="")
        )

    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        if not value:
            return queryset
        return queryset.filter(
            Q(bill_number__icontains=value)
            | Q(patient__first_name__icontains=value)
            | Q(patient__last_name__icontains=value)
            | Q(patient__email__icontains=value)
            | Q(insurance_company__icontains=value)
            | Q(notes__icontains=value)
        )


class PaymentFilterSet(django_filters.FilterSet):
    """FilterSet for Payment filtering"""

    # Date range filters
    start_date = django_filters.DateFilter(
        field_name="payment_date", lookup_expr="date__gte", label="Start Date"
    )
    end_date = django_filters.DateFilter(
        field_name="payment_date", lookup_expr="date__lte", label="End Date"
    )

    # Payment filters
    payment_method = django_filters.ChoiceFilter(
        field_name="payment_method",
        choices=Payment.PAYMENT_METHOD_CHOICES,
        label="Payment Method",
    )
    status = django_filters.ChoiceFilter(
        field_name="status",
        choices=Payment.PAYMENT_STATUS_CHOICES,
        label="Status",
    )

    # Amount filters
    min_amount = django_filters.NumberFilter(
        field_name="amount", lookup_expr="gte", label="Minimum Amount"
    )
    max_amount = django_filters.NumberFilter(
        field_name="amount", lookup_expr="lte", label="Maximum Amount"
    )

    # User filters
    patient_id = django_filters.NumberFilter(
        field_name="patient_id", label="Patient ID"
    )
    bill_id = django_filters.NumberFilter(field_name="bill_id", label="Bill ID")

    # Search filter using method
    search = django_filters.CharFilter(
        method="filter_search", label="Search (payment number, patient, notes)"
    )

    class Meta:
        model = Payment
        fields = [
            "start_date",
            "end_date",
            "payment_method",
            "status",
            "min_amount",
            "max_amount",
            "patient_id",
            "bill_id",
            "search",
        ]

    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        if not value:
            return queryset
        return queryset.filter(
            Q(payment_number__icontains=value)
            | Q(patient__first_name__icontains=value)
            | Q(patient__last_name__icontains=value)
            | Q(patient__email__icontains=value)
            | Q(notes__icontains=value)
        )


class BillingStatsSerializer(serializers.Serializer):
    """Serializer for billing statistics parameters"""

    period = serializers.ChoiceField(
        choices=["today", "week", "month", "year", "all_time"], default="month"
    )
    specialist_id = serializers.IntegerField(required=False)
