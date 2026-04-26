from django.contrib import admin
from django.db.models import Avg, Count, Max, Min
from django.http import HttpRequest
from unfold.admin import ModelAdmin

from apps.bot.models import BotMetrics


@admin.register(BotMetrics)
class BotMetricsAdmin(ModelAdmin):
    change_list_template = "admin/bot/botmetrics/change_list.html"

    list_display = ("metric_name", "value", "created_at")
    list_filter = ("metric_name", "created_at")
    readonly_fields = ("metric_name", "value", "metadata", "created_at", "updated_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    def changelist_view(self, request, extra_context=None):
        qs = BotMetrics.objects.all()

        agg = (
            qs.values("metric_name")
            .annotate(
                total=Count("id"),
                ultima_leitura=Max("created_at"),
                media=Avg("value"),
                minimo=Min("value"),
                maximo=Max("value"),
            )
            .order_by("metric_name")
        )

        # Enriquece cada linha com o valor mais recente (não disponível via Max("value") pois
        # Max retorna o maior, não o último — precisamos buscar pelo created_at mais recente)
        summary = []
        for row in agg:
            latest = (
                qs.filter(metric_name=row["metric_name"])
                .order_by("-created_at")
                .values_list("value", flat=True)
                .first()
            )
            summary.append({**row, "valor_atual": latest})

        extra_context = extra_context or {}
        extra_context["summary"] = summary
        extra_context["total_registros"] = qs.count()
        extra_context["metricas_distintas"] = len(summary)
        extra_context["ultima_atualizacao"] = (
            qs.order_by("-created_at").values_list("created_at", flat=True).first()
        )

        return super().changelist_view(request, extra_context=extra_context)
