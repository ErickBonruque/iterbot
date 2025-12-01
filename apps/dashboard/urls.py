from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_home, name='dashboard_home'),
    path('status/', views.bot_status, name='bot_status'),
    path('bot/configuration/', views.bot_configuration, name='bot_configuration'),
    path('courses/', views.courses_list, name='courses_list'),
    path('courses/<int:course_id>/', views.course_detail, name='course_detail'),
    path('interactions/', views.interactions_log, name='interactions_log'),
    path('users/', views.users_list, name='users_list'),
]
