from django.contrib import admin
from apps.jobs.models import Company, Job, JobApplication


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['nome', 'cnpj', 'email', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['nome', 'cnpj', 'email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'company', 'tipo', 'status', 'created_at']
    list_filter = ['status', 'tipo', 'created_at']
    search_fields = ['titulo', 'descricao', 'company__nome']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ['user', 'job', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__phone_number', 'job__titulo']
    readonly_fields = ['created_at', 'updated_at']
