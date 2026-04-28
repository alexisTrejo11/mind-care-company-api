from django.contrib import admin
from .models import SystemLog


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "created_at",
        "level",
        "logger",
        "message_preview",
        "user",
        "ip_address",
        "request_method",
        "request_path",
    ]
    list_filter = ["level", "logger", "created_at", "request_method"]
    search_fields = ["message", "logger", "module", "function", "request_path"]
    readonly_fields = [
        "level",
        "logger",
        "message",
        "module",
        "function",
        "line",
        "path",
        "exception",
        "user",
        "ip_address",
        "request_method",
        "request_path",
        "created_at",
    ]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    def message_preview(self, obj):
        return obj.message[:100] if obj.message else ""

    message_preview.short_description = "Message Preview"

    def has_add_permission(self, request):
        # Logs should only be created programmatically
        return False

    def has_change_permission(self, request, obj=None):
        # Logs should be read-only
        return False
