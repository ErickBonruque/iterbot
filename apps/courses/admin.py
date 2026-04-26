from django.contrib import admin, messages
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action
from unfold.enums import ActionVariant

from infra.jobspy.service import JobSearchService

from .models import Course, SearchTerm

ACTION_KEY = "courses_searchterm_test_search"


class SearchTermInline(TabularInline):
    model = SearchTerm
    extra = 1
    fields = ("term", "is_default", "priority")


@admin.register(Course)
class CourseAdmin(ModelAdmin):
    """Admin para cursos da UTFPR."""

    list_display = ["name", "code", "level", "modality", "is_active", "order"]
    list_filter = ["is_active", "level", "modality", "created_at"]
    search_fields = ["name", "code", "description"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["order"]
    inlines = [SearchTermInline]

    fieldsets = (
        (None, {"fields": ("name", "code", "description", "is_active", "order")}),
        ("Detalhes", {"fields": ("level", "modality", "duration"), "classes": ("wide",)}),
        ("Datas", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(SearchTerm)
class SearchTermAdmin(ModelAdmin):
    """Admin para termos de busca associados aos cursos."""

    change_form_template = "admin/courses/searchterm/change_form.html"
    actions_submit_line = ["test_search"]

    list_display = ["term", "course", "is_default", "priority"]
    list_filter = ["is_default", "course", "created_at"]
    search_fields = ["term", "course__name"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["priority"]

    fieldsets = (
        ("Identificação", {"fields": ("course", "term", "is_default", "priority")}),
        ("Sites de Busca", {"fields": ("site_name",), "classes": ("wide",)}),
        (
            "Filtros de Busca",
            {
                "fields": ("location", "distance", "job_type", "is_remote", "country_indeed"),
                "classes": ("wide",),
            },
        ),
        (
            "Quantidade e Intervalo",
            {
                "fields": ("results_wanted", "hours_old", "offset"),
                "classes": ("wide",),
            },
        ),
        (
            "LinkedIn Avançado",
            {
                "fields": ("linkedin_fetch_description", "linkedin_company_ids"),
                "classes": ("wide",),
            },
        ),
        ("Datas", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @action(
        description="Testar busca",
        permissions=["test_search"],
        variant=ActionVariant.INFO,
    )
    def test_search(self, request, obj):
        messages.info(request, "Executando busca de vagas... aguarde alguns instantes.")
        service = JobSearchService()
        site_list = [s.strip() for s in obj.site_name.split(",") if s.strip()]
        company_ids = None
        if obj.linkedin_company_ids:
            try:
                company_ids = [
                    int(i.strip()) for i in obj.linkedin_company_ids.split(",") if i.strip()
                ]
            except ValueError:
                company_ids = None
        try:
            results = service.search(
                terms=[obj.term],
                location=obj.location,
                limit=obj.results_wanted,
                hours_old=obj.hours_old,
                site_name=site_list,
                distance=obj.distance,
                job_type=obj.job_type or None,
                is_remote=obj.is_remote,
                country_indeed=obj.country_indeed,
                linkedin_fetch_description=obj.linkedin_fetch_description,
                linkedin_company_ids=company_ids,
                offset=obj.offset,
            )
            request.session["job_search_results"] = results
            if not results:
                messages.warning(
                    request, "Nenhuma vaga encontrada com os parâmetros de busca atuais."
                )
        except Exception as exc:
            request.session["job_search_results"] = []
            messages.warning(request, f"Erro ao executar busca: {exc}")

    def has_test_search_permission(self, request, object_id=None):
        return True

    def changeform_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        if "test_search" in request.GET:
            results = request.session.pop("job_search_results", None)
            if results is not None:
                extra_context["job_results"] = results
        return super().changeform_view(request, object_id, form_url, extra_context)

    def response_change(self, request, obj):
        if ACTION_KEY in request.POST:
            from django.http import HttpResponseRedirect
            from django.urls import reverse

            opts = self.model._meta
            url = reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk])
            return HttpResponseRedirect(url + "?test_search=1")
        return super().response_change(request, obj)
