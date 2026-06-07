from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.bot.models import BotActionLog


@admin.register(BotActionLog)
class BotActionLogAdmin(ModelAdmin):
    list_display = (
        "created_at",
        "action_type",
        "status",
        "user",
        "search_term",
        "jobs_found",
        "duration_ms",
    )
    list_filter = ("action_type", "status", "error_type")
    search_fields = ("user__phone_number", "search_term", "error_message")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    show_full_result_count = False
