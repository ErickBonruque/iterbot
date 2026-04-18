from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from apps.bot.models import BotHealthCheck


@admin.register(BotHealthCheck)
class BotHealthCheckAdmin(ModelAdmin):
    list_display = ("status_badge", "response_time", "session_status", "created_at")
    list_filter = ("status", "created_at")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def status_badge(self, obj):
        colors = {"online": "#28a745", "offline": "#dc3545", "error": "#ffc107"}
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background:{}; color:white; padding:4px 8px; border-radius:3px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"
