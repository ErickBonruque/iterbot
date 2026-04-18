from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.jobs.models.job_search_log import JobSearchLog


@admin.register(JobSearchLog)
class JobSearchLogAdmin(ModelAdmin):
    list_display = ("user", "search_term", "results_count", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__phone_number", "search_term")
    readonly_fields = ("created_at", "updated_at", "filters", "results_preview")
    ordering = ("-created_at",)
