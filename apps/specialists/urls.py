from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.specialists_views import (
    SpecialistPublicViewSet,
    SpecialistManagementViewSet,
)
from .views.company_services_views import ServiceViewSet

router = DefaultRouter()

# Public read-only specialists endpoint
router.register(r"specialists", SpecialistPublicViewSet, basename="specialist-public")
# Management (CRUD) endpoint for specialists
router.register(
    r"specialists-manage",
    SpecialistManagementViewSet,
    basename="specialist-management",
)
router.register(r"services", ServiceViewSet, basename="service")

urlpatterns = [
    path("api/v2/", include(router.urls)),
]
