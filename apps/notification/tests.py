"""
Tests para las tareas de Celery en el módulo de notificaciones
Usando solo Django TestCase sin pytest
"""

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from .tasks import (
    send_notification,
    send_immediate_notification,
    process_notification,
    cleanup_old_notifications,
)
from .models import Notification

User = get_user_model()


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class SendNotificationTests(TestCase):
    """Tests para send_notification"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )
        self.user_id = str(self.user.id)

    @patch("apps.notification.tasks.NotificationService.create_notification")
    def test_send_notification_success(self, mock_create):
        """Verifica envío exitoso de notificación"""
        mock_notif = MagicMock(id=1)
        mock_create.return_value = mock_notif

        result = send_notification(
            template_name="welcome",
            user_id=self.user_id,
            context={"name": "Test"},
        )

        self.assertEqual(result["status"], "queued")
        self.assertEqual(result["notification_id"], 1)
        mock_create.assert_called_once()

    @patch("apps.notification.tasks.NotificationService.create_notification")
    def test_send_notification_with_channels(self, mock_create):
        """Verifica envío con canales específicos"""
        mock_notif = MagicMock(id=2)
        mock_create.return_value = mock_notif

        result = send_notification(
            template_name="alert",
            user_id=self.user_id,
            context={},
            notification_type="email",
        )

        self.assertEqual(result["status"], "queued")
        mock_create.assert_called_once()


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class SendImmediateNotificationTests(TestCase):
    """Tests para send_immediate_notification"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )
        self.user_id = str(self.user.id)

    @patch("apps.notification.tasks.NotificationService.send_immediate_notification")
    def test_send_immediate_notification(self, mock_send):
        """Verifica envío inmediato de notificación"""
        mock_notif = MagicMock(id=3)
        mock_send.return_value = mock_notif

        result = send_immediate_notification(
            title="Alert",
            message="Test message",
            user_id=self.user_id,
        )

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["notification_id"], 3)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class ProcessNotificationTests(TestCase):
    """Tests para process_notification"""

    @patch("apps.notification.tasks.NotificationService.process_notification")
    def test_process_notification_success(self, mock_process):
        """Verifica procesamiento exitoso"""
        mock_process.return_value = True

        result = process_notification(notification_id=1)

        self.assertTrue(result["success"])
        self.assertEqual(result["notification_id"], 1)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class CleanupOldNotificationsTests(TestCase):
    """Tests para cleanup_old_notifications"""

    @patch("apps.notification.tasks.Notification.objects.filter")
    def test_cleanup_success(self, mock_filter):
        """Verifica limpieza exitosa"""
        mock_delete = MagicMock(return_value=(5, {}))
        mock_filter.return_value.delete = mock_delete

        result = cleanup_old_notifications()

        self.assertEqual(result["deleted"], 5)

    @patch("apps.notification.tasks.Notification.objects.filter")
    def test_cleanup_no_items(self, mock_filter):
        """Verifica cuando no hay nada que limpiar"""
        mock_delete = MagicMock(return_value=(0, {}))
        mock_filter.return_value.delete = mock_delete

        result = cleanup_old_notifications()

        self.assertEqual(result["deleted"], 0)
