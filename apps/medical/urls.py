from .views import MedicalRecordViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

router.register(
    r"api/v2/medical-records", MedicalRecordViewSet, basename="medical-record"
)

urlpatterns = router.urls
