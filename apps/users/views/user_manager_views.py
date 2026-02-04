from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAdminUser
from apps.users.models import User
from apps.users.serializers import UserSerializer
from ..services.user_service import UserService


class UserManagerViewSet(ModelViewSet):
    """
    ViewSet for the management of users by admin users.
    Allows admin users to list, create, retrieve, update, and delete users.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        """Optionally filter users by email or phone."""
        queryset = super().get_queryset()
        email = self.request.query_params.get("email")
        phone = self.request.query_params.get("phone")

        if email:
            queryset = queryset.filter(email__iexact=email)
        if phone:
            queryset = queryset.filter(phone=phone)

        return queryset

    def perform_create(self, serializer):
        """
        Create a new user using the UserService.
        If 'superuser' query param is 'true', create a superuser.
        """
        user_data = serializer.validated_data

        if self.request.query_params.get("superuser") == "true":
            user = UserService.register_superuser(**user_data)
        else:
            user, _ = UserService.register_user(**user_data)
        return user

    def perform_update(self, serializer):
        """Update an existing user."""
        serializer.save()

    def perform_destroy(self, instance):
        """Delete an existing user."""
        instance.delete()

    def retrieve(self, request, *args, **kwargs):
        """Retrieve a user by ID."""
        return super().retrieve(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        """List all users, with optional filtering by email or phone."""
        return super().list(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete a user by ID."""
        return super().destroy(request, *args, **kwargs)
