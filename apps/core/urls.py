from django.urls import path
from .views import (
    HealthCheckView,
    ApplicationDocumentationSchemaView,
)

urlpatterns = [
    path("api/v2/health/", HealthCheckView.as_view(), name="health-check"),
    path(
        "api/v2/app-documentation/",
        ApplicationDocumentationSchemaView.as_view(),
        name="app-info",
    ),
]
