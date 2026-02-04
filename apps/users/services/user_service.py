import logging
from typing import Dict, Any, Tuple
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError

from ..models import User
from apps.core.shared import (
    generate_jwt_tokens,
    generate_activation_token,
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
    def register_user(
        **kwargs,
    ) -> Tuple[User, Dict[str, Any]]:
        """
        Registrar nuevo usuario
        Retorna: (user, tokens)
        """
        email = kwargs["email"]
        password = kwargs["password"]
        first_name = kwargs["first_name"]
        last_name = kwargs["last_name"]
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

            user = User.objects.create_user(
                email=email.lower() if email else None,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                user_type=user_type,
                **extra_fields,
            )

            activation_token = generate_activation_token(user)
            logger.info(f"User registered: {user.email} (ID: {user.id})")

            return user, {"activation_token": activation_token}

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
            user.save(update_fields=["is_active"])

            logger.info(f"User activated: {user.email}")

            return user

        except User.DoesNotExist:
            raise UserNotFoundError()

    @staticmethod
    def request_password_reset(email: str) -> str:
        """
        Solicitar reseteo de contraseña
        Retorna: reset_token
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

            # Eliminar token después de uso
            delete_password_reset_token(token)

            logger.info(f"Password reset completed: {user.email}")

            return user

        except User.DoesNotExist:
            raise UserNotFoundError()

    @staticmethod
    def change_password(user: User, current_password: str, new_password: str) -> None:
        """
        Cambiar contraseña (usuario autenticado)
        """
        try:
            # Verificar contraseña actual
            if not user.check_password(current_password):
                raise ValidationError(
                    detail="Current password is incorrect", code="incorrect_password"
                )

            # Verificar que la nueva sea diferente
            if user.check_password(new_password):
                raise ValidationError(
                    detail="New password must be different from current",
                    code="same_password",
                )

            user.set_password(new_password)
            user.save(update_fields=["password"])

            logger.info(f"Password changed: {user.email}")

        except DjangoValidationError as e:
            raise ValidationError(detail=str(e), code="validation_error")

    @staticmethod
    def update_profile(user: User, data: Dict[str, Any]) -> User:
        """
        Actualizar perfil de usuario
        """
        try:
            # Validaciones específicas de negocio
            if "email" in data and data["email"] != user.email:
                if User.objects.filter(email__iexact=data["email"]).exists():
                    raise ValidationError(
                        detail="Email already in use", code="email_in_use"
                    )

            # Actualizar campos permitidos
            allowed_fields = ["first_name", "last_name", "phone", "date_of_birth"]
            update_fields = []

            for field in allowed_fields:
                if field in data:
                    setattr(user, field, data[field])
                    update_fields.append(field)

            if update_fields:
                user.save(update_fields=update_fields)

            logger.info(f"Profile updated: {user.email}")

            return user

        except DjangoValidationError as e:
            raise ValidationError(detail=str(e), code="validation_error")
