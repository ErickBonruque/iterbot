from django.urls import include, path
from django.views.generic import RedirectView

from apps.bot.views import webhook
from apps.core.admin import iterbot_admin
from apps.core.views import HealthCheckView
from apps.users.views import ConfirmEmailView

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path("health/", HealthCheckView.as_view(), name="health"),
    path("admin/", iterbot_admin.urls),
    path("webhook/", webhook),
    path("empresas/", include("apps.companies.urls")),
    path("vagas/", include("apps.jobs.urls")),
    # Aluno não tem login nem cadastro web com senha (usa o WhatsApp); só empresa.
    # Os nomes continuam existindo porque o allauth faz reverse("account_login")
    # por dentro. Ficam antes do include para ganhar do allauth.
    path(
        "accounts/login/",
        RedirectView.as_view(url="/empresas/login/", query_string=True),
        name="account_login",
    ),
    path(
        "accounts/signup/",
        RedirectView.as_view(url="/empresas/signup/", query_string=True),
        name="account_signup",
    ),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("apps.users.urls")),
    path("confirmar-email/<str:token>/", ConfirmEmailView.as_view(), name="confirm_email"),
]
