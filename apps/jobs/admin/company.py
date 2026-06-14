import structlog
from django.contrib import admin, messages
from django.utils import timezone
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
    change_form_show_cancel_button = True
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
        pending = list(queryset.filter(status=CompanyStatus.PENDING).values_list("pk", flat=True))
        updated = queryset.filter(status=CompanyStatus.PENDING).update(
            status=CompanyStatus.APPROVED,
            updated_at=timezone.now(),
        )
        logger.info(
            "companies_approved_bulk",
            count=updated,
            admin_user=request.user.username,
        )
        if updated == 0:
            self.message_user(
                request,
                "Nenhuma empresa estava em estado elegível para aprovação.",
                level=messages.WARNING,
            )
        else:
            self.message_user(
                request,
                f"{updated} empresa(s) aprovada(s) com sucesso.",
                level=messages.SUCCESS,
            )
            try:
                from apps.bot.tasks import notify_company_approved_whatsapp

                for company_id in pending:
                    notify_company_approved_whatsapp.delay(company_id)
            except Exception as exc:
                logger.error("company_approval_notify_dispatch_failed", error=str(exc))

    approve_companies.short_description = "Aprovar empresas selecionadas"

    def block_companies(self, request, queryset):
        updated = queryset.filter(
            status__in=[CompanyStatus.PENDING, CompanyStatus.APPROVED]
        ).update(status=CompanyStatus.BLOCKED, updated_at=timezone.now())
        logger.info(
            "companies_blocked_bulk",
            count=updated,
            admin_user=request.user.username,
        )
        if updated == 0:
            self.message_user(
                request,
                "Nenhuma empresa estava em estado elegível para bloqueio.",
                level=messages.WARNING,
            )
        else:
            self.message_user(
                request,
                f"{updated} empresa(s) bloqueada(s).",
                level=messages.WARNING,
            )

    block_companies.short_description = "Bloquear empresas selecionadas"

    def delete_model(self, request, obj):
        """Deleta a empresa e o auth.User vinculado (limpa allauth EmailAddress por cascade)."""
        user = obj.user
        obj.delete()
        if user is not None:
            user.delete()
            logger.info("company_user_deleted_with_company", admin_user=request.user.username)

    def delete_queryset(self, request, queryset):
        """Deleta em lote: remove auth.User de cada empresa antes de deletar."""
        user_ids = list(queryset.filter(user__isnull=False).values_list("user_id", flat=True))
        queryset.delete()
        if user_ids:
            from django.contrib.auth.models import User as AuthUser

            deleted, _ = AuthUser.objects.filter(pk__in=user_ids).delete()
            logger.info(
                "company_users_deleted_bulk",
                count=deleted,
                admin_user=request.user.username,
            )
