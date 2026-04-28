"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from apps.specialists import urls as specialists_urls
from apps.appointments import urls as appointments_urls
from apps.medical import urls as medical_urls
from apps.billing import urls as billing_urls
from apps.core import urls as core_urls
from django.contrib import admin
from django.urls import path
from apps.users.urls import urlpatterns as users_urls
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from apps.core import urls as core_urls

urlpatterns = [
    path("api/v2/admin/", admin.site.urls),
    path("api/v2/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v2/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/v2/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

urlpatterns += specialists_urls.urlpatterns
urlpatterns += appointments_urls.urlpatterns
urlpatterns += users_urls
urlpatterns += medical_urls.urlpatterns
urlpatterns += billing_urls.urlpatterns
urlpatterns += core_urls.urlpatterns
