from django.contrib import admin
from .models import BotConfiguration, InteractionLog, BotHealthCheck, BotMetrics, BotMessage

@admin.register(BotConfiguration)
class BotConfigurationAdmin(admin.ModelAdmin):
    list_display = ('waha_url', 'updated_at')

@admin.register(InteractionLog)
class InteractionLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'message_type', 'created_at')
    list_filter = ('message_type', 'created_at')
    search_fields = ('message_content', 'user__phone_number')

@admin.register(BotHealthCheck)
class BotHealthCheckAdmin(admin.ModelAdmin):
    list_display = ('status', 'response_time', 'created_at')
    list_filter = ('status', 'created_at')

@admin.register(BotMetrics)
class BotMetricsAdmin(admin.ModelAdmin):
    list_display = ('metric_name', 'value', 'created_at')

@admin.register(BotMessage)
class BotMessageAdmin(admin.ModelAdmin):
    list_display = ('key', 'description', 'updated_at')
    search_fields = ('key', 'text', 'description')
