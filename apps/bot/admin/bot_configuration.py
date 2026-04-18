from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.bot.models import BotConfiguration


@admin.register(BotConfiguration)
class BotConfigurationAdmin(ModelAdmin):
    list_display = ("waha_url", "waha_session", "updated_at")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-updated_at",)
