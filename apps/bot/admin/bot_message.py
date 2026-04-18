from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.bot.models import BotMessage


@admin.register(BotMessage)
class BotMessageAdmin(ModelAdmin):
    list_display = ("key", "description", "updated_at")
    search_fields = ("key", "text", "description")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("key",)
