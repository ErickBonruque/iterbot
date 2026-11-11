from django.urls import path

from apps.jobs import views

app_name = "jobs"

urlpatterns = [
    path("<int:pk>/", views.JobPublicDetailView.as_view(), name="public_detail"),
]
