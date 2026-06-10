from django.urls import path

from apps.users.views import ConfirmCompanyEmailView, ConfirmEmailView, success_page

urlpatterns = [
    path("success/", success_page, name="account_success"),
    path("email-confirmed/", success_page, name="account_email_confirmed_custom"),
    path("confirmar-email/<str:token>/", ConfirmEmailView.as_view(), name="confirm_email"),
    path(
        "confirmar-empresa/<str:token>/",
        ConfirmCompanyEmailView.as_view(),
        name="confirm_company_email",
    ),
]
