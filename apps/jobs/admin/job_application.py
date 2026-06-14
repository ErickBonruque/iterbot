from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.jobs.models.job_application import ApplicationStatus, JobApplication


@admin.register(JobApplication)
class JobApplicationAdmin(ModelAdmin):
    list_display = ("user", "job", "status", "created_at")
    list_filter = ("status", "created_at", "job__company")
    list_editable = ("status",)
    search_fields = ("user__phone_number", "user__email", "job__titulo")
    readonly_fields = ("profile_snapshot", "created_at", "updated_at")
    ordering = ("-created_at",)
    actions = ("mark_as_vista", "mark_as_contatado")

    @admin.action(description="Marcar como Vista")
    def mark_as_vista(self, request, queryset):
        queryset.update(status=ApplicationStatus.VISTA)

    @admin.action(description="Marcar como Contatado")
    def mark_as_contatado(self, request, queryset):
        queryset.update(status=ApplicationStatus.CONTATADO)
