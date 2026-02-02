from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from datetime import date

from apps.core.exceptions.base_exceptions import (
    AuthenticationError,
    ValidationError,
    UserNotFoundError,
    UserAlreadyActiveError,
    InvalidResetTokenError,
)

User = get_user_model()


class UserRegistrationViewTest(TestCase):
    """Test cases for UserRegistrationView"""

    def setUp(self):
        """Set up test client"""
        self.client = APIClient()
        self.url = "/api/v2/auth/register/"

    @patch("apps.users.views.registration_views.send_welcome_email.delay")
    @patch("apps.users.services.user_service.generate_activation_token")
    def test_register_user_success(self, mock_token, mock_email):
        """Test successful user registration"""
        mock_token.return_value = "activation_token_123"

        data = {
            "email": "newuser@test.com",
            "password": "StrongPass123!@#",
            "first_name": "John",
            "last_name": "Doe",
            "phone": "+1234567890",
            "user_type": "patient",
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        self.assertIn("data", response_data)
        self.assertEqual(response_data["data"]["email"], "newuser@test.com")
        self.assertEqual(response_data["data"]["user_type"], "patient")

        # Verify email task was called
        mock_email.assert_called_once()

        # Verify user was created
        user = User.objects.get(email="newuser@test.com")
        self.assertEqual(user.first_name, "John")
        self.assertEqual(user.last_name, "Doe")

    @patch("apps.users.views.registration_views.send_welcome_email.delay")
    @patch("apps.users.services.user_service.generate_activation_token")
    def test_register_specialist_user(self, mock_token, mock_email):
        """Test registering specialist user"""
        mock_token.return_value = "token"

        data = {
            "email": "specialist@test.com",
            "password": "StrongPass123!@#",
            "first_name": "Dr",
            "last_name": "Smith",
            "user_type": "specialist",
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        self.assertEqual(response_data["data"]["user_type"], "specialist")

    def test_register_missing_required_fields(self):
        """Test registration without required fields"""
        data = {
            "email": "incomplete@test.com",
            "password": "StrongPass123!@#",
            # Missing first_name and last_name
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_invalid_email(self):
        """Test registration with invalid email"""
        data = {
            "email": "not-an-email",
            "password": "StrongPass123!@#",
            "first_name": "John",
            "last_name": "Doe",
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_weak_password(self):
        """Test registration with weak password"""
        data = {
            "email": "weak@test.com",
            "password": "123",
            "first_name": "John",
            "last_name": "Doe",
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.users.services.user_service.generate_activation_token")
    def test_register_duplicate_email(self, mock_token):
        """Test registration with duplicate email"""
        mock_token.return_value = "token"

        # Create first user
        User.objects.create_user(
            email="existing@test.com",
            password="testpass123",
            first_name="Existing",
            last_name="User",
        )

        # Try to register with same email
        data = {
            "email": "existing@test.com",
            "password": "StrongPass123!@#",
            "first_name": "New",
            "last_name": "User",
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.users.views.registration_views.send_welcome_email.delay")
    @patch("apps.users.services.user_service.generate_activation_token")
    def test_register_with_optional_fields(self, mock_token, mock_email):
        """Test registration with optional fields"""
        mock_token.return_value = "token"

        data = {
            "email": "complete@test.com",
            "password": "StrongPass123!@#",
            "first_name": "John",
            "last_name": "Doe",
            "phone": "+1234567890",
            "date_of_birth": "1990-01-15",
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email="complete@test.com")
        self.assertEqual(user.phone, "+1234567890")
        self.assertEqual(user.date_of_birth, date(1990, 1, 15))


class UserLoginViewTest(TestCase):
    """Test cases for UserLoginView"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.url = "/api/v2/auth/login/"
        self.user = User.objects.create_user(
            email="testuser@test.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            is_active=True,
        )

    @patch("apps.users.services.user_service.generate_jwt_tokens")
    def test_login_success(self, mock_jwt):
        """Test successful login"""
        mock_jwt.return_value = {
            "access": "access_token_123",
            "refresh": "refresh_token_123",
        }

        data = {"email": "testuser@test.com", "password": "testpass123"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertIn("data", response_data)
        self.assertIn("user", response_data["data"])
        self.assertIn("tokens", response_data["data"])
        self.assertEqual(response_data["data"]["user"]["email"], "testuser@test.com")
        self.assertIn("access", response_data["data"]["tokens"])
        self.assertIn("refresh", response_data["data"]["tokens"])

    def test_login_wrong_password(self):
        """Test login with wrong password"""
        data = {"email": "testuser@test.com", "password": "wrongpassword"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_user(self):
        """Test login with non-existent user"""
        data = {"email": "nonexistent@test.com", "password": "testpass123"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_inactive_user(self):
        """Test login with inactive user"""
        self.user.is_active = False
        self.user.save()

        data = {"email": "testuser@test.com", "password": "testpass123"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_missing_email(self):
        """Test login without email"""
        data = {"password": "testpass123"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_missing_password(self):
        """Test login without password"""
        data = {"email": "testuser@test.com"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_empty_data(self):
        """Test login with empty data"""
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.users.services.user_service.generate_jwt_tokens")
    def test_login_case_insensitive_email(self, mock_jwt):
        """Test login with different email case"""
        mock_jwt.return_value = {"access": "token", "refresh": "token"}

        data = {"email": "TESTUSER@TEST.COM", "password": "testpass123"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class UserLogoutViewTest(TestCase):
    """Test cases for UserLogoutView"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.url = "/api/v2/auth/logout/"
        self.user = User.objects.create_user(
            email="logout@test.com",
            password="testpass123",
            first_name="Logout",
            last_name="User",
            is_active=True,
        )

    @patch("apps.users.views.auth_views.RefreshToken")
    def test_logout_success(self, mock_refresh_token):
        """Test successful logout"""
        self.client.force_authenticate(user=self.user)

        mock_token_instance = MagicMock()
        mock_refresh_token.return_value = mock_token_instance

        data = {"refresh_token": "valid_refresh_token"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_token_instance.blacklist.assert_called_once()

    def test_logout_unauthenticated(self):
        """Test logout without authentication"""
        data = {"refresh_token": "some_token"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_missing_refresh_token(self):
        """Test logout without refresh token"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.users.views.auth_views.RefreshToken")
    def test_logout_invalid_token(self, mock_refresh_token):
        """Test logout with invalid token"""
        self.client.force_authenticate(user=self.user)

        mock_refresh_token.side_effect = Exception("Invalid token")

        data = {"refresh_token": "invalid_token"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EmailActivationViewTest(TestCase):
    """Test cases for EmailActivationView"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.url = "/api/v2/auth/activate/"
        self.user = User.objects.create_user(
            email="inactive@test.com",
            password="testpass123",
            first_name="Inactive",
            last_name="User",
            is_active=False,
        )

    @patch("apps.users.services.user_service.verify_activation_token")
    def test_activate_success(self, mock_verify):
        """Test successful account activation"""
        mock_verify.return_value = self.user.id

        data = {"token": "valid_activation_token"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertIn("email", response_data["data"])

        # Verify user is now active
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    @patch("apps.users.services.user_service.verify_activation_token")
    def test_activate_invalid_token(self, mock_verify):
        """Test activation with invalid token"""
        mock_verify.return_value = None

        data = {"token": "invalid_token"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_activate_missing_token(self):
        """Test activation without token"""
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    @patch("apps.users.services.user_service.verify_activation_token")
    def test_activate_already_active_user(self, mock_verify):
        """Test activation of already active user"""
        self.user.is_active = True
        self.user.save()

        mock_verify.return_value = self.user.id

        data = {"token": "valid_token"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)


class UserProfileViewTest(TestCase):
    """Test cases for UserProfileView"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.url = "/api/v2/auth/profile/"
        self.user = User.objects.create_user(
            email="profile@test.com",
            password="testpass123",
            first_name="Profile",
            last_name="User",
            phone="+1234567890",
            is_active=True,
        )

    def test_get_profile_success(self):
        """Test getting user profile"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertIn("data", response_data)
        self.assertEqual(response_data["data"]["email"], "profile@test.com")
        self.assertEqual(response_data["data"]["first_name"], "Profile")
        self.assertEqual(response_data["data"]["last_name"], "User")

    def test_get_profile_unauthenticated(self):
        """Test getting profile without authentication"""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_profile_patch_success(self):
        """Test partial profile update"""
        self.client.force_authenticate(user=self.user)

        data = {"first_name": "Updated"}

        response = self.client.patch(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["data"]["first_name"], "Updated")

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")

    def test_update_profile_put_success(self):
        """Test full profile update"""
        self.client.force_authenticate(user=self.user)

        data = {
            "first_name": "NewFirst",
            "last_name": "NewLast",
            "phone": "+9876543210",
        }

        response = self.client.put(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["data"]["first_name"], "NewFirst")
        self.assertEqual(response_data["data"]["last_name"], "NewLast")

    def test_update_profile_unauthenticated(self):
        """Test updating profile without authentication"""
        data = {"first_name": "Hacker"}

        response = self.client.patch(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_profile_multiple_fields(self):
        """Test updating multiple fields"""
        self.client.force_authenticate(user=self.user)

        data = {
            "first_name": "Multi",
            "last_name": "Update",
            "phone": "+1111111111",
            "date_of_birth": "1990-05-15",
        }

        response = self.client.patch(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Multi")
        self.assertEqual(self.user.last_name, "Update")
        self.assertEqual(self.user.phone, "+1111111111")


class PasswordResetRequestViewTest(TestCase):
    """Test cases for PasswordResetRequestView"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.url = "/api/v2/auth/password/reset/request/"
        self.user = User.objects.create_user(
            email="reset@test.com",
            password="testpass123",
            first_name="Reset",
            last_name="User",
            is_active=True,
        )

    @patch("apps.users.views.password_views.send_password_reset_email.delay")
    @patch("apps.users.services.user_service.generate_password_reset_token")
    def test_password_reset_request_success(self, mock_token, mock_email):
        """Test successful password reset request"""
        mock_token.return_value = "reset_token_123"

        data = {"email": "reset@test.com"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_email.assert_called_once()

    @patch("apps.users.views.password_views.send_password_reset_email.delay")
    def test_password_reset_request_nonexistent_email(self, mock_email):
        """Test password reset for non-existent email"""
        data = {"email": "nonexistent@test.com"}

        response = self.client.post(self.url, data, format="json")

        # Should return success for security (don't reveal if email exists)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_email.assert_not_called()

    def test_password_reset_request_missing_email(self):
        """Test password reset without email"""
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_request_invalid_email(self):
        """Test password reset with invalid email"""
        data = {"email": "not-an-email"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmViewTest(TestCase):
    """Test cases for PasswordResetConfirmView"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.url = "/api/v2/auth/password/reset/confirm/"
        self.user = User.objects.create_user(
            email="resetconfirm@test.com",
            password="oldpassword",
            first_name="Reset",
            last_name="User",
            is_active=True,
        )

    @patch("apps.users.views.password_views.send_password_changed_notification.delay")
    @patch("apps.users.services.user_service.verify_password_reset_token")
    @patch("apps.users.services.user_service.delete_password_reset_token")
    def test_password_reset_confirm_success(self, mock_delete, mock_verify, mock_email):
        """Test successful password reset"""
        mock_verify.return_value = self.user.id

        data = {"token": "valid_reset_token", "password": "NewStrongPass123!@#"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_email.assert_called_once()

        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPass123!@#"))
        self.assertFalse(self.user.check_password("oldpassword"))

    @patch("apps.users.services.user_service.verify_password_reset_token")
    def test_password_reset_confirm_invalid_token(self, mock_verify):
        """Test password reset with invalid token"""
        mock_verify.return_value = None

        data = {"token": "invalid_token", "password": "NewPassword123!@#"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_password_reset_confirm_missing_token(self):
        """Test password reset without token"""
        data = {"password": "NewPassword123!@#"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_confirm_missing_password(self):
        """Test password reset without password"""
        data = {"token": "valid_token"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.users.services.user_service.verify_password_reset_token")
    def test_password_reset_confirm_weak_password(self, mock_verify):
        """Test password reset with weak password"""
        mock_verify.return_value = self.user.id

        data = {"token": "valid_token", "password": "123"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PasswordChangeViewTest(TestCase):
    """Test cases for PasswordChangeView"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.url = "/api/v2/auth/password/change/"
        self.user = User.objects.create_user(
            email="change@test.com",
            password="currentpassword",
            first_name="Change",
            last_name="User",
            is_active=True,
        )

    @patch("apps.users.views.password_views.send_password_changed_notification.delay")
    def test_password_change_success(self, mock_email):
        """Test successful password change"""
        self.client.force_authenticate(user=self.user)

        data = {
            "current_password": "currentpassword",
            "new_password": "NewPassword123!@#",
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_email.assert_called_once()

        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPassword123!@#"))
        self.assertFalse(self.user.check_password("currentpassword"))

    def test_password_change_unauthenticated(self):
        """Test password change without authentication"""
        data = {
            "current_password": "currentpassword",
            "new_password": "NewPassword123!@#",
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_change_wrong_current_password(self):
        """Test password change with wrong current password"""
        self.client.force_authenticate(user=self.user)

        data = {
            "current_password": "wrongpassword",
            "new_password": "NewPassword123!@#",
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_change_same_password(self):
        """Test password change with same password"""
        self.client.force_authenticate(user=self.user)

        data = {
            "current_password": "currentpassword",
            "new_password": "currentpassword",
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_change_missing_current_password(self):
        """Test password change without current password"""
        self.client.force_authenticate(user=self.user)

        data = {"new_password": "NewPassword123!@#"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_change_missing_new_password(self):
        """Test password change without new password"""
        self.client.force_authenticate(user=self.user)

        data = {"current_password": "currentpassword"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_change_weak_new_password(self):
        """Test password change with weak new password"""
        self.client.force_authenticate(user=self.user)

        data = {"current_password": "currentpassword", "new_password": "123"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserViewsIntegrationTest(TestCase):
    """Integration tests for complete user workflows"""

    def setUp(self):
        """Set up test client"""
        self.client = APIClient()

    @patch("apps.users.views.registration_views.send_welcome_email.delay")
    @patch("apps.users.services.user_service.generate_activation_token")
    @patch("apps.users.services.user_service.verify_activation_token")
    @patch("apps.users.services.user_service.generate_jwt_tokens")
    def test_complete_registration_activation_login_flow(
        self, mock_jwt, mock_verify, mock_activation, mock_email
    ):
        """Test complete user journey: register -> activate -> login"""
        # Step 1: Register
        mock_activation.return_value = "activation_token"

        register_data = {
            "email": "journey@test.com",
            "password": "StrongPass123!@#",
            "first_name": "Journey",
            "last_name": "User",
        }

        response = self.client.post(
            "/api/v2/auth/register/", register_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Get user_id
        user = User.objects.get(email="journey@test.com")

        # Step 2: Activate
        mock_verify.return_value = user.id

        activate_data = {"token": "activation_token"}

        response = self.client.post(
            "/api/v2/auth/activate/", activate_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Step 3: Login
        mock_jwt.return_value = {"access": "token", "refresh": "token"}

        login_data = {"email": "journey@test.com", "password": "StrongPass123!@#"}

        response = self.client.post("/api/v2/auth/login/", login_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", response.json()["data"])

    @patch("apps.users.services.user_service.generate_jwt_tokens")
    def test_login_update_profile_logout_flow(self, mock_jwt):
        """Test flow: login -> update profile -> logout"""
        # Create user
        user = User.objects.create_user(
            email="flow@test.com",
            password="testpass123",
            first_name="Flow",
            last_name="User",
            is_active=True,
        )

        # Step 1: Login
        mock_jwt.return_value = {"access": "access_token", "refresh": "refresh_token"}

        login_data = {"email": "flow@test.com", "password": "testpass123"}

        response = self.client.post("/api/v2/auth/login/", login_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Step 2: Update profile
        self.client.force_authenticate(user=user)

        profile_data = {"first_name": "Updated", "phone": "+1234567890"}

        response = self.client.patch(
            "/api/v2/auth/profile/", profile_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Step 3: Logout
        with patch("apps.users.views.auth_views.RefreshToken") as mock_refresh:
            mock_token = MagicMock()
            mock_refresh.return_value = mock_token

            logout_data = {"refresh_token": "refresh_token"}

            response = self.client.post(
                "/api/v2/auth/logout/", logout_data, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("apps.users.views.password_views.send_password_reset_email.delay")
    @patch("apps.users.views.password_views.send_password_changed_notification.delay")
    @patch("apps.users.services.user_service.generate_password_reset_token")
    @patch("apps.users.services.user_service.verify_password_reset_token")
    @patch("apps.users.services.user_service.delete_password_reset_token")
    @patch("apps.users.services.user_service.generate_jwt_tokens")
    def test_complete_password_reset_flow(
        self,
        mock_jwt,
        mock_delete,
        mock_verify_reset,
        mock_gen_reset,
        mock_notify,
        mock_reset_email,
    ):
        """Test complete password reset: request -> confirm -> login"""
        # Create user
        user = User.objects.create_user(
            email="resetflow@test.com",
            password="oldpassword",
            first_name="Reset",
            last_name="Flow",
            is_active=True,
        )

        # Step 1: Request reset
        mock_gen_reset.return_value = "reset_token"

        request_data = {"email": "resetflow@test.com"}

        response = self.client.post(
            "/api/v2/auth/password/reset/request/", request_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Step 2: Confirm reset
        mock_verify_reset.return_value = user.id

        confirm_data = {"token": "reset_token", "password": "NewPassword123!@#"}

        response = self.client.post(
            "/api/v2/auth/password/reset/confirm/", confirm_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Step 3: Login with new password
        mock_jwt.return_value = {"access": "token", "refresh": "token"}

        login_data = {"email": "resetflow@test.com", "password": "NewPassword123!@#"}

        response = self.client.post("/api/v2/auth/login/", login_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
