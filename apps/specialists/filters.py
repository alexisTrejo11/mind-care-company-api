"""
Filter classes for Specialist model using django-filter.

Provides comprehensive filtering capabilities for specialist listings with
integrated drf-spectacular support for API documentation.
"""

from django_filters import rest_framework as filters
from django.db.models import Q
from .models import Specialist, Service


class SpecialistFilter(filters.FilterSet):
    """
    FilterSet for Specialist model.

    Provides filtering capabilities:
    - specialization: Filter by medical specialization
    - min_rating: Filter by minimum rating (gte)
    - max_rating: Filter by maximum rating (lte)
    - min_fee: Filter by minimum consultation fee (gte)
    - max_fee: Filter by maximum consultation fee (lte)
    - min_experience: Filter by minimum years of experience (gte)
    - max_experience: Filter by maximum years of experience (lte)
    - is_accepting_new_patients: Filter by acceptance status
    - is_active: Filter by active status (admin/management only)
    - search: Custom text search across multiple fields
    - service_id: Filter specialists by offered service
    """

    specialization = filters.ChoiceFilter(
        field_name="specialization",
        choices=Specialist.SPECIALIZATION_CHOICES,
        label="Specialization",
        help_text="Filter by medical specialization",
    )

    min_rating = filters.NumberFilter(
        field_name="rating",
        lookup_expr="gte",
        label="Minimum Rating",
        help_text="Filter by minimum rating (0-5)",
    )
    max_rating = filters.NumberFilter(
        field_name="rating",
        lookup_expr="lte",
        label="Maximum Rating",
        help_text="Filter by maximum rating (0-5)",
    )

    min_fee = filters.NumberFilter(
        field_name="consultation_fee",
        lookup_expr="gte",
        label="Minimum Consultation Fee",
        help_text="Filter by minimum consultation fee",
    )
    max_fee = filters.NumberFilter(
        field_name="consultation_fee",
        lookup_expr="lte",
        label="Maximum Consultation Fee",
        help_text="Filter by maximum consultation fee",
    )

    min_experience = filters.NumberFilter(
        field_name="years_experience",
        lookup_expr="gte",
        label="Minimum Years of Experience",
        help_text="Filter by minimum years of experience",
    )
    max_experience = filters.NumberFilter(
        field_name="years_experience",
        lookup_expr="lte",
        label="Maximum Years of Experience",
        help_text="Filter by maximum years of experience",
    )

    is_accepting_new_patients = filters.BooleanFilter(
        field_name="is_accepting_new_patients",
        label="Accepting New Patients",
        help_text="Filter by patient acceptance status",
    )

    is_active = filters.BooleanFilter(
        field_name="is_active",
        label="Active Status",
        help_text="Filter by active/inactive status",
    )

    search = filters.CharFilter(
        method="filter_search",
        label="Search",
        help_text="Search across name, email, qualifications, and bio",
    )

    service_id = filters.NumberFilter(
        field_name="services__service_id",
        label="Service ID",
        help_text="Filter specialists by offered service",
    )

    class Meta:
        model = Specialist
        fields = []  # Explicit field filtering is handled via filter definitions above

    def filter_search(self, queryset, name, value):
        """
        Custom search filter across multiple fields.

        Searches across:
        - User first name
        - User last name
        - User email
        - Qualifications
        - Bio
        """
        if not value:
            return queryset

        return queryset.filter(
            Q(user__first_name__icontains=value)
            | Q(user__last_name__icontains=value)
            | Q(user__email__icontains=value)
            | Q(qualifications__icontains=value)
            | Q(bio__icontains=value)
        )


class ServiceFilter(filters.FilterSet):
    """
    FilterSet for Service model.

    Provides filtering capabilities:
    - category: Filter by service category
    - is_active: Filter by active/inactive status
    - min_duration: Filter by minimum service duration
    - max_duration: Filter by maximum service duration
    - min_price: Filter by minimum service price
    - max_price: Filter by maximum service price
    - search: Custom text search across name, description, and category
    """

    category = filters.ChoiceFilter(
        field_name="category",
        choices=Service.CATEGORY_CHOICES,
        label="Category",
        help_text="Filter by service category",
    )

    is_active = filters.BooleanFilter(
        field_name="is_active",
        label="Active Status",
        help_text="Filter by active/inactive status",
    )

    min_duration = filters.NumberFilter(
        field_name="duration_minutes",
        lookup_expr="gte",
        label="Minimum Duration",
        help_text="Filter by minimum service duration in minutes",
    )
    max_duration = filters.NumberFilter(
        field_name="duration_minutes",
        lookup_expr="lte",
        label="Maximum Duration",
        help_text="Filter by maximum service duration in minutes",
    )

    min_price = filters.NumberFilter(
        field_name="base_price",
        lookup_expr="gte",
        label="Minimum Price",
        help_text="Filter by minimum service price",
    )

    max_price = filters.NumberFilter(
        field_name="base_price",
        lookup_expr="lte",
        label="Maximum Price",
        help_text="Filter by maximum service price",
    )

    search = filters.CharFilter(
        method="filter_search",
        label="Search",
        help_text="Search across name, description, and category",
    )

    class Meta:
        model = Service
        fields = []  # Explicit field filtering is handled via filter definitions above

    def filter_search(self, queryset, name, value):
        """
        Custom search filter across multiple fields.

        Searches across:
        - Service name
        - Service description
        - Service category
        """
        if not value:
            return queryset

        return queryset.filter(
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(category__icontains=value)
        )
