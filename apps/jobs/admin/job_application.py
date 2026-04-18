from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.jobs.models.job_application import JobApplication


@admin.register(JobApplication)
class JobApplicationAdmin(ModelAdmin):
    list_display = ("user", "job", "created_at")
    list_filter = ("created_at", "job__company")
    search_fields = ("user__phone_number", "user__email", "job__titulo")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
