from django.urls import path

from apps.users.views import success_page

urlpatterns = [
    path("success/", success_page, name="account_success"),
    path("email-confirmed/", success_page, name="account_email_confirmed_custom"),
]
