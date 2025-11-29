"""
Serializers para a API REST do dashboard.
"""
from rest_framework import serializers
from apps.courses.models import Course, SearchTerm
from apps.bot.models import InteractionLog, BotHealthCheck, BotMetrics, BotConfiguration
from apps.users.models import UserProfile


class SearchTermSerializer(serializers.ModelSerializer):
    """Serializer para termos de busca."""
    
    class Meta:
        model = SearchTerm
        fields = ['id', 'course', 'term', 'is_default', 'priority', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class CourseSerializer(serializers.ModelSerializer):
    """Serializer para cursos."""
    search_terms = SearchTermSerializer(many=True, read_only=True)
    search_terms_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = [
            'id', 'name', 'code', 'description', 'is_active', 'order',
            'search_terms', 'search_terms_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_search_terms_count(self, obj):
        return obj.search_terms.count()


class CourseListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listagem de cursos."""
    search_terms_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = ['id', 'name', 'code', 'is_active', 'order', 'search_terms_count']
    
    def get_search_terms_count(self, obj):
        return obj.search_terms.count()


class InteractionLogSerializer(serializers.ModelSerializer):
    """Serializer para logs de interação."""
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)
    user_ra = serializers.CharField(source='user.ra', read_only=True)
    
    class Meta:
        model = InteractionLog
        fields = [
            'id', 'user', 'user_phone', 'user_ra', 'message_content',
            'message_type', 'session_id', 'metadata', 'created_at'
        ]
        read_only_fields = ['created_at']


class BotHealthCheckSerializer(serializers.ModelSerializer):
    """Serializer para verificações de saúde do bot."""
    
    class Meta:
        model = BotHealthCheck
        fields = [
            'id', 'status', 'response_time', 'error_message',
            'session_status', 'created_at'
        ]
        read_only_fields = ['created_at']


class BotMetricsSerializer(serializers.ModelSerializer):
    """Serializer para métricas do bot."""
    
    class Meta:
        model = BotMetrics
        fields = ['id', 'metric_name', 'value', 'metadata', 'created_at']
        read_only_fields = ['created_at']


class BotStatusSerializer(serializers.Serializer):
    """Serializer para status atual do bot."""
    status = serializers.ChoiceField(choices=['online', 'offline', 'error'])
    response_time = serializers.FloatField(allow_null=True)
    session_status = serializers.CharField()
    last_check = serializers.DateTimeField()
    error_message = serializers.CharField(allow_null=True, required=False)
    uptime_percentage = serializers.FloatField(required=False)
    avg_response_time = serializers.FloatField(required=False)
    total_checks = serializers.IntegerField(required=False)
    error_count = serializers.IntegerField(required=False)


class BotConfigurationSerializer(serializers.ModelSerializer):
    """Serializer para configurar credenciais do bot/WAHA."""

    class Meta:
        model = BotConfiguration
        fields = [
            "id",
            "waha_url",
            "waha_api_key",
            "waha_session",
            "dashboard_username",
            "dashboard_password",
            "admin_username",
            "admin_password",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
