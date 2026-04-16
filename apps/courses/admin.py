from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Course, SearchTerm


class SearchTermInline(admin.TabularInline):
    model = SearchTerm
    extra = 1
    fields = ('term', 'is_default', 'priority')


@admin.register(Course)
class CourseAdmin(ModelAdmin):
    """Admin para cursos da UTFPR."""
    list_display = ['name', 'code', 'level', 'modality', 'is_active', 'order']
    list_filter = ['is_active', 'level', 'modality', 'created_at']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['order']
    inlines = [SearchTermInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'description', 'is_active', 'order')
        }),
        ('Detalhes', {
            'fields': ('level', 'modality', 'duration'),
            'classes': ('wide',)
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SearchTerm)
class SearchTermAdmin(ModelAdmin):
    """Admin para termos de busca associados aos cursos."""
    list_display = ['term', 'course', 'is_default', 'priority']
    list_filter = ['is_default', 'course', 'created_at']
    search_fields = ['term', 'course__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['priority']
    
    fieldsets = (
        (None, {
            'fields': ('course', 'term', 'is_default', 'priority')
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
