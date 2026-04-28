from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock
from datetime import datetime, date

from apps.users.services.user_service import UserService
from apps.core.exceptions.base_exceptions import (
    AuthenticationError,
    ValidationError,
    UserNotFoundError,
    UserAlreadyActiveError,
    InvalidResetTokenError,
)

User = get_user_model()


class UserServiceRegisterTest(TestCase):
    """Test cases for UserService.register_user"""

    def test_register_user_success(self):
        """Test successful user registration"""
        with patch(
            "apps.users.services.user_service.generate_activation_token"
        ) as mock_token:
            mock_token.return_value = "test_activation_token"

            user, tokens = UserService.register_user(
                email="newuser@test.com",
                password="testpass123",
                first_name="John",
                last_name="Doe",
                phone="+1234567890",
                user_type="patient",
            )

            self.assertIsNotNone(user)
            self.assertEqual(user.email, "newuser@test.com")
            self.assertEqual(user.first_name, "John")
            self.assertEqual(user.last_name, "Doe")
            self.assertEqual(user.phone, "+1234567890")
            self.assertEqual(user.user_type, "patient")
            self.assertTrue(user.check_password("testpass123"))
            self.assertIn("activation_token", tokens)
            self.assertEqual(tokens["activation_token"], "test_activation_token")

    def test_register_user_email_normalization(self):
        """Test that email is normalized to lowercase"""
        with patch("apps.users.services.user_service.generate_activation_token"):
            user, _ = UserService.register_user(
                email="UpperCase@TEST.com",
                password="testpass123",
                first_name="Test",
                last_name="User",
            )

            self.assertEqual(user.email, "uppercase@test.com")

    def test_register_user_default_user_type(self):
        """Test that default user_type is patient"""
        with patch("apps.users.services.user_service.generate_activation_token"):
            user, _ = UserService.register_user(
                email="patient@test.com",
                password="testpass123",
                first_name="Test",
                last_name="Patient",
            )

            self.assertEqual(user.user_type, "patient")

    def test_register_user_duplicate_email(self):
        """Test registration with duplicate email fails"""
        with patch("apps.users.services.user_service.generate_activation_token"):
            # Create first user
            UserService.register_user(
                email="duplicate@test.com",
                password="testpass123",
                first_name="First",
                last_name="User",
            )

            # Try to create second user with same email
            with self.assertRaises(ValidationError) as context:
                UserService.register_user(
                    email="duplicate@test.com",
                    password="testpass456",
                    first_name="Second",
                    last_name="User",
                )

            self.assertIn("already registered", str(context.exception.detail).lower())

    def test_register_user_duplicate_email_case_insensitive(self):
        """Test that duplicate email check is case-insensitive"""
        with patch("apps.users.services.user_service.generate_activation_token"):
            UserService.register_user(
                email="test@example.com",
                password="testpass123",
                first_name="First",
                last_name="User",
            )

            with self.assertRaises(ValidationError):
                UserService.register_user(
                    email="TEST@EXAMPLE.COM",
                    password="testpass456",
                    first_name="Second",
                    last_name="User",
                )

    def test_register_user_without_optional_fields(self):
        """Test registration without optional fields"""
        with patch("apps.users.services.user_service.generate_activation_token"):
            user, _ = UserService.register_user(
                email="minimal@test.com",
                password="testpass123",
                first_name="Minimal",
                last_name="User",
            )

            self.assertIsNone(user.phone)
            self.assertEqual(user.user_type, "patient")

    def test_register_user_with_extra_fields(self):
        """Test registration with extra fields"""
        with patch("apps.users.services.user_service.generate_activation_token"):
            user, _ = UserService.register_user(
                email="extra@test.com",
                password="testpass123",
                first_name="Extra",
                last_name="User",
                date_of_birth=date(1990, 1, 1),
            )

            self.assertEqual(user.date_of_birth, date(1990, 1, 1))


class UserServiceAuthenticationTest(TestCase):
    """Test cases for UserService.authenticate_user"""

    def setUp(self):
        """Set up test user"""
        self.user = User.objects.create_user(
            email="testuser@test.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            is_active=True,
        )

    def test_authenticate_user_success(self):
        """Test successful authentication"""
        with patch("apps.users.services.user_service.generate_jwt_tokens") as mock_jwt:
            mock_jwt.return_value = {
                "access": "access_token",
                "refresh": "refresh_token",
            }

            user, tokens = UserService.authenticate_user(
                email="testuser@test.com", password="testpass123"
            )

            self.assertEqual(user.email, "testuser@test.com")
            self.assertIn("access", tokens)
            self.assertIn("refresh", tokens)

            # Verify last_login was updated
            user.refresh_from_db()
            self.assertIsNotNone(user.last_login)

    def test_authenticate_user_email_case_insensitive(self):
        """Test that authentication is case-insensitive for email"""
        with patch("apps.users.services.user_service.generate_jwt_tokens") as mock_jwt:
            mock_jwt.return_value = {"access": "token", "refresh": "token"}

            user, _ = UserService.authenticate_user(
                email="TESTUSER@TEST.COM", password="testpass123"
            )

            self.assertEqual(user.email, "testuser@test.com")

    def test_authenticate_user_email_with_spaces(self):
        """Test that email spaces are stripped"""
        with patch("apps.users.services.user_service.generate_jwt_tokens") as mock_jwt:
            mock_jwt.return_value = {"access": "token", "refresh": "token"}

            user, _ = UserService.authenticate_user(
                email="  testuser@test.com  ", password="testpass123"
            )

            self.assertIsNotNone(user)

    def test_authenticate_user_invalid_email(self):
        """Test authentication with non-existent email"""
        with self.assertRaises(AuthenticationError) as context:
            UserService.authenticate_user(
                email="nonexistent@test.com", password="testpass123"
            )

        self.assertIn("invalid credentials", str(context.exception.detail).lower())

    def test_authenticate_user_wrong_password(self):
        """Test authentication with wrong password"""
        with self.assertRaises(AuthenticationError) as context:
            UserService.authenticate_user(
                email="testuser@test.com", password="wrongpassword"
            )

        self.assertIn("invalid credentials", str(context.exception.detail).lower())

    def test_authenticate_user_inactive_account(self):
        """Test authentication with inactive account"""
        self.user.is_active = False
        self.user.save()

        with self.assertRaises(AuthenticationError) as context:
            UserService.authenticate_user(
                email="testuser@test.com", password="testpass123"
            )

        self.assertIn("not active", str(context.exception.detail).lower())

    def test_authenticate_user_updates_last_login(self):
        """Test that authentication updates last_login"""
        with patch("apps.users.services.user_service.generate_jwt_tokens") as mock_jwt:
            mock_jwt.return_value = {"access": "token", "refresh": "token"}

            old_last_login = self.user.last_login

            UserService.authenticate_user(
                email="testuser@test.com", password="testpass123"
            )

            self.user.refresh_from_db()
            self.assertIsNotNone(self.user.last_login)
            self.assertNotEqual(self.user.last_login, old_last_login)


class UserServiceActivationTest(TestCase):
    """Test cases for UserService.activate_user"""

    def setUp(self):
        """Set up test user"""
        self.user = User.objects.create_user(
            email="inactive@test.com",
            password="testpass123",
            first_name="Inactive",
            last_name="User",
            is_active=False,
        )

    def test_activate_user_success(self):
        """Test successful user activation"""
        with patch(
            "apps.users.services.user_service.verify_activation_token"
        ) as mock_verify:
            mock_verify.return_value = self.user.id

            activated_user = UserService.activate_user("valid_token")

            self.assertEqual(activated_user.id, self.user.id)
            self.assertTrue(activated_user.is_active)

            # Verify in database
            self.user.refresh_from_db()
            self.assertTrue(self.user.is_active)

    def test_activate_user_invalid_token(self):
        """Test activation with invalid token"""
        with patch(
            "apps.users.services.user_service.verify_activation_token"
        ) as mock_verify:
            mock_verify.return_value = None

            with self.assertRaises(InvalidResetTokenError) as context:
                UserService.activate_user("invalid_token")

            self.assertIn("invalid", str(context.exception.detail).lower())

    def test_activate_user_already_active(self):
        """Test activation of already active user"""
        self.user.is_active = True
        self.user.save()

        with patch(
            "apps.users.services.user_service.verify_activation_token"
        ) as mock_verify:
            mock_verify.return_value = self.user.id

            with self.assertRaises(UserAlreadyActiveError):
                UserService.activate_user("valid_token")

    def test_activate_user_nonexistent_user(self):
        """Test activation with token for non-existent user"""
        with patch(
            "apps.users.services.user_service.verify_activation_token"
        ) as mock_verify:
            mock_verify.return_value = 99999  # Non-existent user_id

            with self.assertRaises(UserNotFoundError):
                UserService.activate_user("valid_token")


class UserServicePasswordResetRequestTest(TestCase):
    """Test cases for UserService.request_password_reset"""

    def setUp(self):
        """Set up test user"""
        self.user = User.objects.create_user(
            email="reset@test.com",
            password="testpass123",
            first_name="Reset",
            last_name="User",
            is_active=True,
        )

    def test_request_password_reset_success(self):
        """Test successful password reset request"""
        with patch(
            "apps.users.services.user_service.generate_password_reset_token"
        ) as mock_token:
            mock_token.return_value = "reset_token_123"

            token = UserService.request_password_reset("reset@test.com")

            self.assertEqual(token, "reset_token_123")
            mock_token.assert_called_once_with(self.user)

    def test_request_password_reset_email_normalization(self):
        """Test that email is normalized"""
        with patch(
            "apps.users.services.user_service.generate_password_reset_token"
        ) as mock_token:
            mock_token.return_value = "reset_token"

            token = UserService.request_password_reset("  RESET@TEST.COM  ")

            self.assertEqual(token, "reset_token")

    def test_request_password_reset_nonexistent_email(self):
        """Test password reset request for non-existent email"""
        # Should return empty string for security (don't reveal if email exists)
        token = UserService.request_password_reset("nonexistent@test.com")

        self.assertEqual(token, "")

    def test_request_password_reset_inactive_user(self):
        """Test password reset request for inactive user"""
        self.user.is_active = False
        self.user.save()

        # Should return empty string (inactive users can't reset password)
        token = UserService.request_password_reset("reset@test.com")

        self.assertEqual(token, "")


class UserServicePasswordResetTest(TestCase):
    """Test cases for UserService.reset_password"""

    def setUp(self):
        """Set up test user"""
        self.user = User.objects.create_user(
            email="resetpwd@test.com",
            password="oldpassword",
            first_name="Reset",
            last_name="User",
            is_active=True,
        )

    def test_reset_password_success(self):
        """Test successful password reset"""
        with patch(
            "apps.users.services.user_service.verify_password_reset_token"
        ) as mock_verify:
            with patch(
                "apps.users.services.user_service.delete_password_reset_token"
            ) as mock_delete:
                mock_verify.return_value = self.user.id

                user = UserService.reset_password("valid_token", "newpassword123")

                self.assertEqual(user.id, self.user.id)
                self.assertTrue(user.check_password("newpassword123"))
                self.assertFalse(user.check_password("oldpassword"))

                mock_delete.assert_called_once_with("valid_token")

    def test_reset_password_invalid_token(self):
        """Test password reset with invalid token"""
        with patch(
            "apps.users.services.user_service.verify_password_reset_token"
        ) as mock_verify:
            mock_verify.return_value = None

            with self.assertRaises(InvalidResetTokenError) as context:
                UserService.reset_password("invalid_token", "newpassword")

            self.assertIn("invalid", str(context.exception.detail).lower())

    def test_reset_password_nonexistent_user(self):
        """Test password reset for non-existent user"""
        with patch(
            "apps.users.services.user_service.verify_password_reset_token"
        ) as mock_verify:
            mock_verify.return_value = 99999

            with self.assertRaises(UserNotFoundError):
                UserService.reset_password("valid_token", "newpassword")

    def test_reset_password_inactive_user(self):
        """Test password reset for inactive user"""
        self.user.is_active = False
        self.user.save()

        with patch(
            "apps.users.services.user_service.verify_password_reset_token"
        ) as mock_verify:
            mock_verify.return_value = self.user.id

            with self.assertRaises(UserNotFoundError):
                UserService.reset_password("valid_token", "newpassword")

    def test_reset_password_token_deleted_after_use(self):
        """Test that reset token is deleted after successful reset"""
        with patch(
            "apps.users.services.user_service.verify_password_reset_token"
        ) as mock_verify:
            with patch(
                "apps.users.services.user_service.delete_password_reset_token"
            ) as mock_delete:
                mock_verify.return_value = self.user.id

                UserService.reset_password("valid_token", "newpassword")

                mock_delete.assert_called_once_with("valid_token")


class UserServiceChangePasswordTest(TestCase):
    """Test cases for UserService.change_password"""

    def setUp(self):
        """Set up test user"""
        self.user = User.objects.create_user(
            email="changepwd@test.com",
            password="currentpassword",
            first_name="Change",
            last_name="User",
        )

    def test_change_password_success(self):
        """Test successful password change"""
        UserService.change_password(
            self.user, current_password="currentpassword", new_password="newpassword123"
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpassword123"))
        self.assertFalse(self.user.check_password("currentpassword"))

    def test_change_password_wrong_current_password(self):
        """Test password change with wrong current password"""
        with self.assertRaises(ValidationError) as context:
            UserService.change_password(
                self.user,
                current_password="wrongpassword",
                new_password="newpassword123",
            )

        self.assertIn("incorrect", str(context.exception.detail).lower())

        # Verify password hasn't changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("currentpassword"))

    def test_change_password_same_as_current(self):
        """Test password change with same password"""
        with self.assertRaises(ValidationError) as context:
            UserService.change_password(
                self.user,
                current_password="currentpassword",
                new_password="currentpassword",
            )

        self.assertIn("different", str(context.exception.detail).lower())

    def test_change_password_updates_only_password(self):
        """Test that only password field is updated"""
        old_email = self.user.email
        old_first_name = self.user.first_name

        UserService.change_password(
            self.user, current_password="currentpassword", new_password="newpassword123"
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, old_email)
        self.assertEqual(self.user.first_name, old_first_name)


class UserServiceUpdateProfileTest(TestCase):
    """Test cases for UserService.update_profile"""

    def setUp(self):
        """Set up test user"""
        self.user = User.objects.create_user(
            email="profile@test.com",
            password="testpass123",
            first_name="Original",
            last_name="Name",
            phone="+1234567890",
        )

    def test_update_profile_first_name(self):
        """Test updating first name"""
        updated_user = UserService.update_profile(self.user, {"first_name": "Updated"})

        self.assertEqual(updated_user.first_name, "Updated")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")

    def test_update_profile_last_name(self):
        """Test updating last name"""
        updated_user = UserService.update_profile(
            self.user, {"last_name": "NewLastName"}
        )

        self.assertEqual(updated_user.last_name, "NewLastName")

    def test_update_profile_phone(self):
        """Test updating phone"""
        updated_user = UserService.update_profile(self.user, {"phone": "+9876543210"})

        self.assertEqual(updated_user.phone, "+9876543210")

    def test_update_profile_date_of_birth(self):
        """Test updating date of birth"""
        updated_user = UserService.update_profile(
            self.user, {"date_of_birth": date(1990, 5, 15)}
        )

        self.assertEqual(updated_user.date_of_birth, date(1990, 5, 15))

    def test_update_profile_multiple_fields(self):
        """Test updating multiple fields at once"""
        updated_user = UserService.update_profile(
            self.user,
            {"first_name": "Multi", "last_name": "Update", "phone": "+1111111111"},
        )

        self.assertEqual(updated_user.first_name, "Multi")
        self.assertEqual(updated_user.last_name, "Update")
        self.assertEqual(updated_user.phone, "+1111111111")

    def test_update_profile_empty_data(self):
        """Test updating with empty data"""
        old_first_name = self.user.first_name

        updated_user = UserService.update_profile(self.user, {})

        self.assertEqual(updated_user.first_name, old_first_name)

    def test_update_profile_ignores_disallowed_fields(self):
        """Test that disallowed fields are ignored"""
        old_email = self.user.email
        old_password = self.user.password

        UserService.update_profile(
            self.user,
            {
                "first_name": "Updated",
                "password": "hacked_password",
                "is_staff": True,
                "user_type": "admin",
            },
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(self.user.email, old_email)
        self.assertEqual(self.user.password, old_password)
        self.assertFalse(self.user.is_staff)
        self.assertNotEqual(self.user.user_type, "admin")

    def test_update_profile_duplicate_email(self):
        """Test updating to duplicate email"""
        # Create another user
        User.objects.create_user(
            email="other@test.com",
            password="testpass123",
            first_name="Other",
            last_name="User",
        )

        # Email updates are ignored as per allowed_fields
        # But if email was in allowed_fields, this would test the validation
        old_email = self.user.email
        UserService.update_profile(self.user, {"email": "other@test.com"})

        # Email shouldn't change because it's not in allowed_fields
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, old_email)


class UserServiceIntegrationTest(TestCase):
    """Integration tests for complete user workflows"""

    def test_complete_registration_activation_flow(self):
        """Test complete flow: register -> activate -> login"""
        # Register
        with patch(
            "apps.users.services.user_service.generate_activation_token"
        ) as mock_activation:
            mock_activation.return_value = "activation_token"

            user, tokens = UserService.register_user(
                email="flow@test.com",
                password="testpass123",
                first_name="Flow",
                last_name="User",
            )

            self.assertIsNotNone(user)
            self.assertFalse(user.is_active)  # Default is False

        # Activate
        with patch(
            "apps.users.services.user_service.verify_activation_token"
        ) as mock_verify:
            mock_verify.return_value = user.id

            activated_user = UserService.activate_user("activation_token")
            self.assertTrue(activated_user.is_active)

        # Login
        with patch("apps.users.services.user_service.generate_jwt_tokens") as mock_jwt:
            mock_jwt.return_value = {"access": "token", "refresh": "token"}

            auth_user, jwt_tokens = UserService.authenticate_user(
                email="flow@test.com", password="testpass123"
            )

            self.assertEqual(auth_user.id, user.id)
            self.assertIn("access", jwt_tokens)

    def test_complete_password_reset_flow(self):
        """Test complete flow: request reset -> reset password -> login"""
        # Create user
        user = User.objects.create_user(
            email="resetflow@test.com",
            password="oldpassword",
            first_name="Reset",
            last_name="Flow",
        )
        user.is_active = True
        user.save()

        # Request reset
        with patch(
            "apps.users.services.user_service.generate_password_reset_token"
        ) as mock_token:
            mock_token.return_value = "reset_token"

            token = UserService.request_password_reset("resetflow@test.com")
            self.assertEqual(token, "reset_token")

        # Reset password
        with patch(
            "apps.users.services.user_service.verify_password_reset_token"
        ) as mock_verify:
            with patch("apps.users.services.user_service.delete_password_reset_token"):
                mock_verify.return_value = user.id

                UserService.reset_password("reset_token", "newpassword123")

        # Login with new password
        with patch("apps.users.services.user_service.generate_jwt_tokens") as mock_jwt:
            mock_jwt.return_value = {"access": "token", "refresh": "token"}

            auth_user, _ = UserService.authenticate_user(
                email="resetflow@test.com", password="newpassword123"
            )

            self.assertEqual(auth_user.id, user.id)

        # Verify old password doesn't work
        with self.assertRaises(AuthenticationError):
            UserService.authenticate_user(
                email="resetflow@test.com", password="oldpassword"
            )

    def test_profile_update_after_login(self):
        """Test updating profile after successful login"""
        # Create and login
        user = User.objects.create_user(
            email="updateflow@test.com",
            password="testpass123",
            first_name="Original",
            last_name="Name",
            is_active=True,
        )

        with patch("apps.users.services.user_service.generate_jwt_tokens") as mock_jwt:
            mock_jwt.return_value = {"access": "token", "refresh": "token"}

            auth_user, _ = UserService.authenticate_user(
                email="updateflow@test.com", password="testpass123"
            )

        # Update profile
        updated_user = UserService.update_profile(
            auth_user,
            {"first_name": "Updated", "last_name": "Profile", "phone": "+1234567890"},
        )

        self.assertEqual(updated_user.first_name, "Updated")
        self.assertEqual(updated_user.last_name, "Profile")
        self.assertEqual(updated_user.phone, "+1234567890")
