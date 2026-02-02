"""
User Authentication Serializers
Handles serialization for signup, login, password reset, and user profile
"""

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )
    user_type = serializers.ChoiceField(
        choices=[("patient", "Patient"), ("specialist", "Specialist")],
        default="patient",
    )

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "first_name",
            "last_name",
            "phone",
            "date_of_birth",
            "user_type",
        ]
        extra_kwargs = {
            "first_name": {"required": True},
            "last_name": {"required": True},
        }


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )

    def validate(self, attrs):
        """Validate credentials and authenticate user"""
        email = attrs.get("email", "").lower()
        password = attrs.get("password")

        if email and password:
            if len(email) > 255:
                raise serializers.ValidationError(
                    "Email length must not exceed 255 characters."
                )
            if len(password) > 128:
                raise serializers.ValidationError(
                    "Password length must not exceed 128 characters."
                )

            return attrs
        else:
            raise serializers.ValidationError("Must include 'email' and 'password'.")


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile information"""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "date_of_birth",
            "user_type",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "email",
            "user_type",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_full_name(self, obj):
        """Get user's full name"""
        return obj.get_full_name()


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request"""

    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """Validate email exists"""
        email = value.lower()
        if not User.objects.filter(email=email).exists():
            # Don't reveling if email existence for security reasons
            # Still validate format
            pass
        return email


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation"""

    token = serializers.CharField(required=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )

    def validate_old_password(self, value):
        """Validate old password is correct"""
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for changing password while logged in"""

    old_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    new_password_confirm = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )

    def validate_old_password(self, value):
        """Validate old password is correct"""
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate(self, attrs):
        """Validate new passwords match"""
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password": "Password fields didn't match."}
            )
        return attrs


class EmailActivationSerializer(serializers.Serializer):
    """Serializer for email activation"""

    token = serializers.CharField(required=True)


class TokenRefreshSerializer(serializers.Serializer):
    """Serializer for refreshing JWT tokens"""

    refresh = serializers.CharField(required=True)

    def validate(self, attrs):
        """Validate and refresh token"""
        refresh = RefreshToken(attrs["refresh"])
        attrs["access"] = str(refresh.access_token)
        return attrs
