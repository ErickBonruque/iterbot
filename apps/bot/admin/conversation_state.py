from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.bot.models.conversation_state import ConversationState


@admin.register(ConversationState)
class ConversationStateAdmin(ModelAdmin):
    list_display = ["user", "current_action", "selected_course", "updated_at"]
    list_filter = ["current_action"]
    search_fields = ["user__phone_number", "user__ra"]
    raw_id_fields = ["user", "selected_course", "selected_term"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Usuário", {"fields": ("user",)}),
        ("Estado", {"fields": ("current_action", "flow_data")}),
        (
            "Preferências",
            {"fields": ("selected_course", "selected_term"), "classes": ("collapse",)},
        ),
        ("Datas", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
