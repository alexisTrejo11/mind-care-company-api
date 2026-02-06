from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.specialists_views import (
    SpecialistPublicViewSet,
    SpecialistManagementViewSet,
)
from .views.company_services_views import ServiceViewSet

router = DefaultRouter()

router.register(r"specialists", SpecialistPublicViewSet, basename="specialist-public")
router.register(
    r"specialists",
    SpecialistManagementViewSet,
    basename="specialist-management",
)
router.register(r"services", ServiceViewSet, basename="service")

urlpatterns = [
    path("api/v2/", include(router.urls)),
]
