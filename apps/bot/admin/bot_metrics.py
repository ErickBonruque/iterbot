from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.bot.models import BotMetrics


@admin.register(BotMetrics)
class BotMetricsAdmin(ModelAdmin):
    list_display = ("metric_name", "value", "created_at")
    list_filter = ("metric_name", "created_at")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
