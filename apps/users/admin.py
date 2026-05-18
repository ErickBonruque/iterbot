from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from unfold.admin import ModelAdmin

from apps.courses.models import Course

from .models import UserProfile


class CoursePreferenceFilter(SimpleListFilter):
    title = "Por curso"
    parameter_name = "course"

    def lookups(self, request, model_admin):
        courses = Course.objects.filter(is_active=True).order_by("order", "name")
        choices = [(str(c.pk), c.name) for c in courses]
        choices.insert(0, ("none", "Sem curso definido"))
        return choices

    def queryset(self, request, queryset):
        if self.value() == "none":
            return queryset.filter(course__isnull=True)
        if self.value():
            return queryset.filter(course_id=self.value())
        return queryset


@admin.register(UserProfile)
class UserProfileAdmin(ModelAdmin):
    """Admin para perfis de usuários/alunos."""

    list_display = [
        "phone_number",
        "email",
        "ra",
        "course_name",
        "is_authenticated_utfpr",
        "last_activity",
    ]
    list_filter = [CoursePreferenceFilter, "is_authenticated_utfpr", "last_activity", "created_at"]
    search_fields = ["phone_number", "email", "ra", "user__username"]
    readonly_fields = ["created_at", "updated_at", "last_activity"]
    ordering = ["-last_activity"]

    fieldsets = (
        ("Dados Pessoais", {"fields": ("user", "phone_number", "email", "ra", "course")}),
        (
            "Autenticação UTFPR",
            {"fields": ("is_authenticated_utfpr", "utfpr_password"), "classes": ("wide",)},
        ),
        (
            "Datas",
            {"fields": ("created_at", "updated_at", "last_activity"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Curso Preferido", ordering="course__name")
    def course_name(self, obj):
        return obj.course.name if obj.course_id else "—"

    def has_delete_permission(self, request, obj=None):
        return False
