from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.specialists_views import SpecialistViewSet
from .views.clinic_services_views import ServiceViewSet

router = DefaultRouter()


router.register(r"specialists", SpecialistViewSet, basename="specialist")
router.register(r"services", ServiceViewSet, basename="service")

urlpatterns = [
    path("api/v2/", include(router.urls)),
]
