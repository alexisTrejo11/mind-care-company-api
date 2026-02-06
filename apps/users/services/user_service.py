import logging
from typing import Dict, Any, Tuple
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError

from ..models import User
from apps.core.shared import (
    generate_jwt_tokens,
    verify_activation_token,
    generate_password_reset_token,
    verify_password_reset_token,
    delete_password_reset_token,
)
from apps.core.exceptions.base_exceptions import (
    AuthenticationError,
    ValidationError,
    UserNotFoundError,
    UserAlreadyActiveError,
    InvalidResetTokenError,
)

logger = logging.getLogger(__name__)


class UserService:
    """Servicio para operaciones de usuario"""

    @staticmethod
    def validate_user_register(
        **kwargs,
    ) -> None:
        """
        Validar date user registration data. Checks for email and phone uniqueness. And Password strength. Raises ValidationError if any validation fails.
        Returns None if all validations pass.
        """
        email = kwargs["email"]
        phone = kwargs.get("phone")
        user_type = kwargs.get("user_type", "patient")
        date_of_birth = kwargs.get("date_of_birth")

        extra_fields = {
            "date_of_birth": date_of_birth,
        }
        try:
            if User.objects.filter(email__iexact=email).exists():
                raise ValidationError(
                    detail="Email already registered", code="email_exists"
                )

            if phone:
                exists = User.objects.filter(phone=phone).exists()
                if exists:
                    raise ValidationError(
                        detail="Phone number already registered", code="phone_exists"
                    )

            from django.contrib.auth.password_validation import validate_password

            validate_password(kwargs["password"], user=None)
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e), code="validation_error")
        except Exception as e:
            logger.error(f"Registration error: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def register_superuser(**kwargs) -> User:
        """
        Registrar superusuario/admin
        """
        email = kwargs["email"]
        password = kwargs["password"]
        first_name = kwargs["first_name"]
        last_name = kwargs["last_name"]
        phone = kwargs.get("phone")

        try:
            if User.objects.filter(email__iexact=email).exists():
                raise ValidationError(
                    detail="Email already registered", code="email_exists"
                )

            if phone:
                exists = User.objects.filter(phone=phone).exists()
                if exists:
                    raise ValidationError(
                        detail="Phone number already registered", code="phone_exists"
                    )

            user = User.objects.create_superuser(
                email=email.lower() if email else None,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )

            logger.info(f"Superuser registered: {user.email} (ID: {user.id})")

            return user

        except DjangoValidationError as e:
            raise ValidationError(detail=str(e), code="validation_error")
        except Exception as e:
            logger.error(f"Superuser registration error: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def authenticate_user(email: str, password: str) -> Tuple[User, Dict[str, str]]:
        """
        Autenticar usuario y generar tokens JWT
        """
        try:
            # Normalizar email
            email = email.lower().strip()

            # Buscar usuario
            user = User.objects.filter(email=email).first()

            if not user:
                raise AuthenticationError(
                    detail="Invalid credentials", code="invalid_credentials"
                )

            # Verificar si está activo
            if not user.is_active:
                raise AuthenticationError(
                    detail="Account is not active", code="account_inactive"
                )

            # Verificar password
            if not user.check_password(password):
                raise AuthenticationError(
                    detail="Invalid credentials", code="invalid_credentials"
                )

            # Actualizar último login
            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])

            # Generar tokens JWT
            tokens = generate_jwt_tokens(user)

            logger.info(f"User authenticated: {user.email}")

            return user, tokens

        except DjangoValidationError as e:
            raise ValidationError(detail=str(e), code="validation_error")

    @staticmethod
    def activate_user(token: str) -> User:
        """
        Activar usuario mediante token
        """
        try:
            user_id = verify_activation_token(token)

            if not user_id:
                raise InvalidResetTokenError(
                    detail="Invalid or expired activation token"
                )

            user = User.objects.get(id=user_id)

            if user.is_active:
                raise UserAlreadyActiveError()

            user.is_active = True
            logger.info(f"User activated: {user.email}")

            return user

        except User.DoesNotExist:
            raise UserNotFoundError()

    @staticmethod
    def new_password_reset_token(email: str) -> str:
        """
        Request password reset email
        Returns: reset_token
        """
        try:
            email = email.lower().strip()
            user = User.objects.filter(email=email, is_active=True).first()

            # Por seguridad, siempre retornamos éxito
            if not user:
                logger.info(f"Password reset requested for non-existent email: {email}")
                return ""

            reset_token = generate_password_reset_token(user)

            logger.info(f"Password reset requested: {user.email}")

            return reset_token

        except Exception as e:
            logger.error(f"Password reset request error: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def reset_password(token: str, new_password: str) -> User:
        """
        Resetear contraseña con token
        """
        try:
            user_id = verify_password_reset_token(token)

            if not user_id:
                raise InvalidResetTokenError(detail="Invalid or expired reset token")

            user = User.objects.get(id=user_id, is_active=True)
            user.set_password(new_password)

            user.save(update_fields=["password"])

            delete_password_reset_token(token)

            logger.info(f"Password reset completed: {user.email}")

            return user
        except User.DoesNotExist:
            raise UserNotFoundError()

    @staticmethod
    def change_password(user: User, current_password: str, new_password: str) -> User:
        """
        Change user password. Requires current password for verification.
        """
        try:
            if not user.check_password(current_password):
                raise ValidationError(
                    detail="Current password is incorrect", code="incorrect_password"
                )

            if user.check_password(new_password):
                raise ValidationError(
                    detail="New password must be different from current",
                    code="same_password",
                )

            from django.contrib.auth.password_validation import validate_password

            validate_password(new_password, user=user)
            user.set_password(new_password)

            logger.info(f"Password changed: {user.email}")
            return user

        except DjangoValidationError as e:
            raise ValidationError(detail=str(e), code="validation_error")

    @staticmethod
    def update_profile(user: User, data: Dict[str, Any]) -> Tuple[User, list]:
        """
        Update user profile. Only allows updating specific fields.
        Returns: (updated_user, updated_fields)
        """
        try:
            allowed_fields = ["first_name", "last_name", "date_of_birth"]
            update_fields = []

            for field in allowed_fields:
                if field in data:
                    setattr(user, field, data[field])
                    update_fields.append(field)

            logger.info(f"Profile updated: {user.email}")

            return user, update_fields
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e), code="validation_error")
