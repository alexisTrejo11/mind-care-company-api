"""
Filter classes for Appointment model using django-filter.

Provides comprehensive filtering capabilities for appointment listings with
integrated drf-spectacular support for API documentation.
"""

from django_filters import rest_framework as filters
from django.db.models import Q
from .models import Appointment


class AppointmentFilter(filters.FilterSet):
    """
    FilterSet for Appointment model.

    Provides filtering capabilities:
    - status: Filter by appointment status (exact or multiple)
    - appointment_type: Filter by appointment type
    - appointment_date: Filter by appointment date (gte, lte, exact)
    - specialist: Filter by specialist ID
    - patient: Filter by patient ID
    """

    status = filters.CharFilter(
        field_name="status",
        lookup_expr="exact",
        label="Status",
        help_text="Filter by appointment status",
    )

    appointment_type = filters.CharFilter(
        field_name="appointment_type",
        lookup_expr="exact",
        label="Appointment Type",
        help_text="Filter by appointment type",
    )

    appointment_date = filters.DateFromToRangeFilter(
        field_name="appointment_date",
        label="Appointment Date",
        help_text="Filter by appointment date range",
    )

    specialist = filters.NumberFilter(
        field_name="specialist__id",
        lookup_expr="exact",
        label="Specialist",
        help_text="Filter by specialist ID",
    )

    patient = filters.NumberFilter(
        field_name="patient__id",
        lookup_expr="exact",
        label="Patient",
        help_text="Filter by patient ID",
    )

    class Meta:
        model = Appointment
        fields = []
