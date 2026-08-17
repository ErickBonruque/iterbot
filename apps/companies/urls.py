from django.urls import path
from django.views.generic import RedirectView

from apps.companies import views

app_name = "companies"

urlpatterns = [
    # /empresas/ nunca teve view propria e devolvia 404 para quem digitava o
    # endereco "raiz" do portal; manda para a porta de entrada de fato.
    path(
        "",
        RedirectView.as_view(pattern_name="companies:login", permanent=False),
        name="index",
    ),
    path("signup/", views.CompanySignupView.as_view(), name="signup"),
    path("login/", views.CompanyLoginView.as_view(), name="login"),
    path("logout/", views.CompanyLogoutView.as_view(), name="logout"),
    path("criar/", views.CompanyCreateView.as_view(), name="company_create"),
    path("perfil/", views.CompanyProfileView.as_view(), name="profile"),
    path("vagas/nova/", views.JobCreateView.as_view(), name="job_create"),
    path("vagas/<int:pk>/editar/", views.JobUpdateView.as_view(), name="job_update"),
    path("vagas/<int:pk>/deletar/", views.JobDeleteView.as_view(), name="job_delete"),
    path("candidaturas/", views.JobApplicationsListView.as_view(), name="applications"),
    path(
        "candidaturas/<int:pk>/status/",
        views.JobApplicationStatusUpdateView.as_view(),
        name="application_status",
    ),
]
