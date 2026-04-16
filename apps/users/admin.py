from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from unfold.admin import ModelAdmin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(ModelAdmin):
    """Admin para perfis de usuários/alunos."""
    list_display = ['phone_number', 'email', 'ra', 'is_authenticated_utfpr', 'last_activity']
    list_filter = ['is_authenticated_utfpr', 'last_activity', 'created_at']
    search_fields = ['phone_number', 'email', 'ra', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'last_activity']
    ordering = ['-last_activity']
    
    fieldsets = (
        ('Dados Pessoais', {
            'fields': ('user', 'phone_number', 'email', 'ra')
        }),
        ('Autenticação UTFPR', {
            'fields': ('is_authenticated_utfpr', 'utfpr_password'),
            'classes': ('wide',)
        }),
        ('Preferências', {
            'fields': ('selected_course', 'selected_term'),
            'classes': ('collapse',)
        }),
        ('Dados do Fluxo', {
            'fields': ('current_action', 'flow_data'),
            'classes': ('collapse',)
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at', 'last_activity'),
            'classes': ('collapse',)
        }),
    )

    def has_delete_permission(self, request, obj=None):
        return False
