from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from unfold.admin import ModelAdmin
from unfold.decorators import action
from unfold.enums import ActionVariant

from apps.jobs.models.daily_job import DailyJob


@admin.register(DailyJob)
class DailyJobAdmin(ModelAdmin):
    list_display = (
        "title",
        "company",
        "search_term",
        "fetched_date",
        "job_type",
        "is_manual",
        "created_at",
    )
    list_filter = (
        "fetched_date",
        "search_term__course",
        "search_term",
        "is_manual",
    )
    search_fields = ("title", "company", "search_term__term")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-fetched_date", "title")
    date_hierarchy = "fetched_date"
    actions_list = ["trigger_fetch_daily_jobs"]
    actions_submit_line = ["mark_as_manual"]

    @action(description="Buscar Vagas Agora", variant=ActionVariant.SUCCESS)
    def trigger_fetch_daily_jobs(self, request):
        from apps.jobs.tasks import fetch_daily_jobs

        fetch_daily_jobs.delay()
        self.message_user(
            request,
            "Task de busca de vagas disparada. Aguarde alguns minutos e recarregue a página.",
            level=messages.SUCCESS,
        )
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "."))

    @action(
        description="Marcar como Manual",
        permissions=["change"],
        variant=ActionVariant.INFO,
    )
    def mark_as_manual(self, request, obj):
        obj.is_manual = True
        obj.save(update_fields=["is_manual", "updated_at"])
        self.message_user(request, f'Vaga "{obj.title}" marcada como manual.')

    def has_mark_as_manual_permission(self, request, object_id=None):
        return True
