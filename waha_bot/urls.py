from django.urls import include, path
from django.views.generic import RedirectView

from apps.bot.views import webhook
from apps.core.admin import iterbot_admin
from apps.core.views import HealthCheckView
from apps.users.views import ConfirmEmailView

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path("health/", HealthCheckView.as_view(), name="health"),
    path("api/", include("apps.dashboard.api_urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("admin/", iterbot_admin.urls),
    path("webhook/", webhook),
    path("empresas/", include("apps.companies.urls")),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("apps.users.urls")),
    path("confirmar-email/<str:token>/", ConfirmEmailView.as_view(), name="confirm_email"),
]
