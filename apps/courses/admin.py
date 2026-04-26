from django.contrib import admin
from django.contrib import messages
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
                    int(i.strip())
                    for i in obj.linkedin_company_ids.split(",")
                    if i.strip()
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
            self._test_search_results = results
        except Exception as exc:
            self._test_search_results = []
            messages.warning(request, f"Erro ao executar busca: {exc}")

    def has_test_search_permission(self, request, object_id=None):
        return True

    def response_change(self, request, obj):
        if ACTION_KEY in request.POST:
            results = getattr(self, "_test_search_results", None)
            if results is None:
                return super().response_change(request, obj)
            if not results:
                messages.warning(
                    request, "Nenhuma vaga encontrada com os parâmetros de busca atuais."
                )
            from django.template.response import TemplateResponse

            context = self.admin_site.each_context(request)
            context.update(
                {
                    "add": False,
                    "change": True,
                    "has_view_permission": self.has_view_permission(request, obj),
                    "has_change_permission": self.has_change_permission(request, obj),
                    "has_delete_permission": self.has_delete_permission(request, obj),
                    "has_add_permission": self.has_add_permission(request),
                    "has_editable_inline_admin_formsets": False,
                    "original": obj,
                    "object_id": str(obj.pk),
                    "opts": self.model._meta,
                    "is_popup": False,
                    "save_as": False,
                    "show_save": True,
                    "show_save_and_continue": True,
                    "show_delete": self.has_delete_permission(request, obj),
                    "show_save_as_new": False,
                    "title": f"Alterar {self.model._meta.verbose_name}",
                    "job_results": results,
                }
            )
            return TemplateResponse(request, self.change_form_template, context)
        return super().response_change(request, obj)