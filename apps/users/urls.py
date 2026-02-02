from .views import (
    UserLoginView,
    UserLogoutView,
    UserProfileView,
    UserRegistrationView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    EmailActivationView,
)
from django.urls import path

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
