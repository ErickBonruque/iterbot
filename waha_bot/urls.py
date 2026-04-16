from django.urls import include, path
from django.views.generic import RedirectView

from apps.bot.views import webhook
from apps.core.admin import capyvagas_admin
from apps.core.views import HealthCheckView

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path("health/", HealthCheckView.as_view(), name="health"),
    path("api/", include("apps.dashboard.api_urls")),
    path("admin/", capyvagas_admin.urls),
    path("webhook/", webhook),
    path("empresas/", include("apps.companies.urls")),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("apps.users.urls")),
]
