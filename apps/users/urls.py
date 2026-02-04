from .views import (
    UserLoginView,
    UserLogoutView,
    UserProfileView,
    UserRegistrationView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    EmailActivationView,
    UserManagerViewSet,
)
from django.urls import path
from django.urls import include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"api/v2/auth/users", UserManagerViewSet, basename="user-manager")

urlpatterns = [
    path("api/v2/auth/login/", UserLoginView.as_view(), name="user-login"),
    path("api/v2/auth/logout/", UserLogoutView.as_view(), name="user-logout"),
    path("api/v2/auth/register/", UserRegistrationView.as_view(), name="user-register"),
    path("api/v2/auth/profile/", UserProfileView.as_view(), name="user-profile"),
    path(
        "api/v2/auth/password/change/",
        PasswordChangeView.as_view(),
        name="password-change",
    ),
    path(
        "api/v2/auth/password/reset/request/",
        PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),
    path(
        "api/v2/auth/password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("api/v2/auth/activate/", EmailActivationView.as_view(), name="email-activate"),
]
urlpatterns += router.urls
