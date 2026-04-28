from rest_framework import viewsets
from apps.core.permissions import IsAdminOrStaff
from .models import Notification
from .serializers import NotificationSerializer


class NotificationModelViewSet(viewsets.ModelViewSet):
    """
    A viewset for viewing and editing notification instances.
    """

    permission_classes = [IsAdminOrStaff]
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
