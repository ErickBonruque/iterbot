from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from apps.bot.views import webhook
from apps.core.views import HealthCheckView
from apps.core.admin import capyvagas_admin

urlpatterns = [
    path('', RedirectView.as_view(url='/admin/', permanent=False)),
    path('health/', HealthCheckView.as_view(), name='health'),
    path('admin/', capyvagas_admin.urls),
    path('webhook/', webhook),
    path('empresas/', include('apps.companies.urls')),
    path('accounts/', include('allauth.urls')),
    path('accounts/', include('apps.users.urls')),
]
