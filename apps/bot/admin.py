from django.contrib import admin
from django.utils.html import escape, format_html, mark_safe
from unfold.admin import ModelAdmin

from .models import BotConfiguration, BotHealthCheck, BotMessage, BotMetrics, InteractionLog


@admin.register(BotConfiguration)
class BotConfigurationAdmin(ModelAdmin):
    list_display = ("waha_url", "waha_session", "updated_at")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-updated_at",)


@admin.register(InteractionLog)
class InteractionLogAdmin(ModelAdmin):
    list_display = ("user", "message_type_badge", "message_preview", "session_short", "created_at")
    list_filter = ("message_type", "created_at", "session_id")
    search_fields = ("message_content", "user__phone_number", "session_id")
    readonly_fields = ("created_at", "updated_at", "conversation_timeline")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def session_short(self, obj):
        """Return shortened session ID for display"""
        return obj.session_id[:20] + ("..." if len(obj.session_id) > 20 else "")

    session_short.short_description = "Sessão"

    def message_type_badge(self, obj):
        color = "#17a2b8" if obj.message_type == "SENT" else "#6c757d"
        label = "Bot" if obj.message_type == "SENT" else "Usuario"
        return format_html(
            '<span style="background:{}; color:white; padding:4px 8px; border-radius:3px;">{}</span>',
            color,
            label,
        )

    message_type_badge.short_description = "Tipo"

    def message_preview(self, obj):
        return obj.message_content[:80] + ("..." if len(obj.message_content) > 80 else "")

    message_preview.short_description = "Mensagem"

    def conversation_timeline(self, obj):
        """Exibe toda a conversa do usuario em formato timeline."""
        logs = InteractionLog.objects.filter(user=obj.user).order_by("created_at")[:100]

        html_parts = ['<div style="max-height:500px; overflow-y:auto; padding:10px;">']
        for log in logs:
            is_current = log.pk == obj.pk
            if log.message_type == "SENT":
                align = "right"
                bg = "#d1ecf1"
                label = "Bot"
            else:
                align = "left"
                bg = "#f8f9fa"
                label = "Usuário"

            border = "2px solid #ffc107" if is_current else "none"
            html_parts.append(
                f'<div style="text-align:{align}; margin-bottom:8px;">'
                f'<div style="display:inline-block; max-width:70%; background:{bg}; '
                f'padding:8px 12px; border-radius:8px; border:{border}; text-align:left;">'
                f'<small style="color:#6c757d;"><strong>{label}</strong> — '
                f'{log.created_at.strftime("%d/%m %H:%M")}</small><br>'
                f'{escape(log.message_content)}'
                f'</div></div>'
            )
        html_parts.append("</div>")
        return mark_safe("".join(html_parts))

    conversation_timeline.short_description = "Conversa Completa"

    fieldsets = (
        (
            "Mensagem",
            {"fields": ("user", "message_type", "message_content", "session_id", "metadata")},
        ),
        ("Timeline da Conversa", {"fields": ("conversation_timeline",), "classes": ("wide",)}),
        ("Datas", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


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


@admin.register(BotMetrics)
class BotMetricsAdmin(ModelAdmin):
    list_display = ("metric_name", "value", "created_at")
    list_filter = ("metric_name", "created_at")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(BotMessage)
class BotMessageAdmin(ModelAdmin):
    list_display = ("key", "description", "updated_at")
    search_fields = ("key", "text", "description")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("key",)
