"""
User Authentication Views
Views limpias que solo orquestan servicios
"""

from .auth_views import UserLoginView, UserLogoutView
from .profile_views import UserProfileView
from .registration_views import UserRegistrationView
from .password_views import (
    PasswordResetRequestView,
    PasswordResetConfirmView,
    PasswordChangeView,
)
from .activation_views import EmailActivationView


all = [
    UserLoginView,
    UserLogoutView,
    UserRegistrationView,
    UserProfileView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    PasswordChangeView,
    EmailActivationView,
]
