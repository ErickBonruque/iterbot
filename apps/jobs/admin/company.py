import structlog
from django.contrib import admin, messages
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from apps.jobs.models.company import Company, CompanyStatus

logger = structlog.get_logger(__name__)


@admin.register(Company)
class CompanyAdmin(ModelAdmin):
    list_display = ("nome", "cnpj", "email", "telefone", "status_badge", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("nome", "cnpj", "email", "contato_nome")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    actions = ["approve_companies", "block_companies"]
    fieldsets = (
        (
            "Dados da Empresa",
            {"fields": ("nome", "cnpj", "email", "telefone", "endereco", "descricao")},
        ),
        ("Responsavel", {"fields": ("contato_nome", "contato_cargo")}),
        ("Status", {"fields": ("status", "user")}),
        ("Datas", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def status_badge(self, obj):
        colors = {
            CompanyStatus.PENDING: "#ffc107",
            CompanyStatus.APPROVED: "#28a745",
            CompanyStatus.BLOCKED: "#dc3545",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background:{}; color:white; padding:4px 8px; border-radius:3px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def approve_companies(self, request, queryset):
        updated = queryset.filter(status=CompanyStatus.PENDING).update(
            status=CompanyStatus.APPROVED
        )
        logger.info(
            "companies_approved_bulk",
            count=updated,
            admin_user=request.user.username,
        )
        self.message_user(
            request,
            f"{updated} empresa(s) aprovada(s) com sucesso.",
            level=messages.SUCCESS,
        )

    approve_companies.short_description = "Aprovar empresas selecionadas"

    def block_companies(self, request, queryset):
        updated = queryset.filter(
            status__in=[CompanyStatus.PENDING, CompanyStatus.APPROVED]
        ).update(status=CompanyStatus.BLOCKED)
        logger.info(
            "companies_blocked_bulk",
            count=updated,
            admin_user=request.user.username,
        )
        self.message_user(
            request,
            f"{updated} empresa(s) bloqueada(s).",
            level=messages.WARNING,
        )

    block_companies.short_description = "Bloquear empresas selecionadas"
