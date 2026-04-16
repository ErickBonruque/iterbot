from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import action
from unfold.enums import ActionVariant

from apps.jobs.models import Company, Job, JobApplication, JobSearchLog, CompanyStatus, JobStatus


@admin.register(Company)
class CompanyAdmin(ModelAdmin):
    list_display = ('nome', 'cnpj', 'email', 'telefone', 'status_badge', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('nome', 'cnpj', 'email', 'contato_nome')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    fieldsets = (
        ('Dados da Empresa', {
            'fields': ('nome', 'cnpj', 'email', 'telefone', 'endereco', 'descricao')
        }),
        ('Responsavel', {
            'fields': ('contato_nome', 'contato_cargo')
        }),
        ('Status', {
            'fields': ('status', 'user')
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        colors = {
            CompanyStatus.PENDING: '#ffc107',
            CompanyStatus.APPROVED: '#28a745',
            CompanyStatus.BLOCKED: '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{}; color:white; padding:4px 8px; border-radius:3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(Job)
class JobAdmin(ModelAdmin):
    list_display = ('titulo', 'company', 'tipo', 'status_badge', 'created_at')
    list_filter = ('status', 'tipo', 'company', 'created_at')
    search_fields = ('titulo', 'descricao', 'company__nome')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    actions_submit_line = ['approve_job', 'reject_job']

    def status_badge(self, obj):
        colors = {
            JobStatus.DRAFT: '#6c757d',
            JobStatus.PENDING: '#ffc107',
            JobStatus.APPROVED: '#28a745',
            JobStatus.REJECTED: '#dc3545',
            JobStatus.EXPIRED: '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{}; color:white; padding:4px 8px; border-radius:3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    fieldsets = (
        (None, {
            'fields': ('company', 'titulo', 'descricao', 'requisitos', 'salario', 'tipo')
        }),
        ('Status', {
            'fields': ('status', 'rejection_reason'),
            'classes': ('wide',),
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @action(
        description='Aprovar Vaga',
        permissions=['approve_job'],
        variant=ActionVariant.SUCCESS,
    )
    def approve_job(self, request, obj):
        obj.status = JobStatus.APPROVED
        obj.rejection_reason = ''
        obj.save(update_fields=['status', 'rejection_reason'])
        self.message_user(request, f'Vaga "{obj.titulo}" aprovada com sucesso.')

    def has_approve_job_permission(self, request, object_id=None):
        return True

    @action(
        description='Rejeitar Vaga',
        permissions=['reject_job'],
        variant=ActionVariant.DANGER,
    )
    def reject_job(self, request, obj):
        obj.status = JobStatus.REJECTED
        obj.save(update_fields=['status', 'rejection_reason'])
        self.message_user(request, f'Vaga "{obj.titulo}" foi rejeitada.')

    def has_reject_job_permission(self, request, object_id=None):
        return True


@admin.register(JobApplication)
class JobApplicationAdmin(ModelAdmin):
    list_display = ('user', 'job', 'created_at')
    list_filter = ('created_at', 'job__company')
    search_fields = ('user__phone_number', 'user__email', 'job__titulo')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)


@admin.register(JobSearchLog)
class JobSearchLogAdmin(ModelAdmin):
    list_display = ('user', 'search_term', 'results_count', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__phone_number', 'search_term')
    readonly_fields = ('created_at', 'updated_at', 'filters', 'results_preview')
    ordering = ('-created_at',)
