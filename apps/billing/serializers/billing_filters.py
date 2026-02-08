from rest_framework import serializers
from datetime import datetime, date
from decimal import Decimal
from typing import Optional


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
