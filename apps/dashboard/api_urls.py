"""
URLs da API REST para o dashboard.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.dashboard.api_views import (
    CourseViewSet,
    SearchTermViewSet,
    InteractionLogViewSet,
    BotStatusViewSet,
    BotConfigurationViewSet,
    UserProfileViewSet,
)

# Router para viewsets
router = DefaultRouter()
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'terms', SearchTermViewSet, basename='term')
router.register(r'interactions', InteractionLogViewSet, basename='interaction')
router.register(r'bot/status', BotStatusViewSet, basename='bot-status')
router.register(r'bot/configuration', BotConfigurationViewSet, basename='bot-configuration')
router.register(r'users', UserProfileViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
]
