from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from apps.bot.views import webhook
from apps.core.views import HealthCheckView

urlpatterns = [
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
    path('health/', HealthCheckView.as_view(), name='health'),
    path('admin/', admin.site.urls),
    path('webhook/', webhook),
    path('dashboard/', include('apps.dashboard.urls')),
    path('api/', include('apps.dashboard.api_urls')),
]
