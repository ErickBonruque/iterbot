"""
Views da API REST para o dashboard.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny  # TODO: Adicionar autenticação em produção
from django.utils import timezone
from datetime import timedelta
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.contrib.auth import get_user_model

from apps.courses.models import Course, SearchTerm
from apps.users.models import UserProfile
from apps.bot.models import InteractionLog, BotHealthCheck, BotMetrics, BotConfiguration
from apps.bot.health import BotHealthMonitor
from apps.dashboard.serializers import (
    CourseSerializer,
    CourseListSerializer,
    SearchTermSerializer,
    InteractionLogSerializer,
    BotHealthCheckSerializer,
    BotStatusSerializer,
    BotConfigurationSerializer,
    UserProfileSerializer,
    UserProfileListSerializer,
)


class CourseViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciamento de cursos.
    
    list: Listar todos os cursos
    create: Criar novo curso
    retrieve: Obter detalhes de um curso
    update: Atualizar curso
    partial_update: Atualizar parcialmente curso
    destroy: Deletar curso
    """
    queryset = Course.objects.all()
    permission_classes = [AllowAny]  # TODO: Adicionar autenticação
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'code']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'order', 'created_at']
    ordering = ['order', 'name']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CourseListSerializer
        return CourseSerializer
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Alternar status ativo/inativo do curso."""
        course = self.get_object()
        course.is_active = not course.is_active
        course.save()
        return Response({
            'id': course.id,
            'is_active': course.is_active,
            'message': f"Curso {'ativado' if course.is_active else 'desativado'} com sucesso"
        })
    
    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """Deletar múltiplos cursos de uma vez."""
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'Nenhum ID fornecido'}, status=status.HTTP_400_BAD_REQUEST)
        
        count = Course.objects.filter(id__in=ids).delete()[0]
        return Response({'message': f'{count} curso(s) deletado(s) com sucesso', 'count': count})


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.select_related("selected_course").all()
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_authenticated_utfpr", "selected_course"]
    search_fields = ["phone_number", "ra"]
    ordering_fields = ["last_activity", "created_at", "ra", "phone_number"]
    ordering = ["-last_activity"]

    def get_serializer_class(self):
        if self.action == "list":
            return UserProfileListSerializer
        return UserProfileSerializer


class SearchTermViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciamento de termos de busca.
    """
    queryset = SearchTerm.objects.all()
    serializer_class = SearchTermSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['course', 'is_default']
    ordering_fields = ['priority', 'term', 'created_at']
    ordering = ['-priority', 'term']
    
    @action(detail=False, methods=['get'])
    def by_course(self, request):
        """Obter termos de busca de um curso específico."""
        course_id = request.query_params.get('course_id')
        if not course_id:
            return Response({'error': 'course_id é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)
        
        terms = self.queryset.filter(course_id=course_id)
        serializer = self.get_serializer(terms, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def toggle_default(self, request, pk=None):
        """Alternar status padrão/ativo do termo."""
        term = self.get_object()
        term.is_default = not term.is_default
        term.save()
        return Response({
            'id': term.id,
            'is_default': term.is_default,
            'message': f"Termo {'ativado' if term.is_default else 'desativado'} com sucesso"
        })
    
    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Reordenar termos de busca."""
        order_data = request.data.get('order', [])  # [{'id': 1, 'priority': 10}, ...]
        
        for item in order_data:
            SearchTerm.objects.filter(id=item['id']).update(priority=item['priority'])
        
        return Response({'message': 'Ordem atualizada com sucesso'})


class InteractionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para visualização de logs de interação (somente leitura).
    """
    queryset = InteractionLog.objects.select_related('user')
    serializer_class = InteractionLogSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user', 'message_type', 'session_id']
    search_fields = ['message_content', 'user__phone_number', 'user__ra']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Estatísticas dos logs de interação."""
        days = int(request.query_params.get('days', 7))
        since = timezone.now() - timedelta(days=days)
        
        logs = self.queryset.filter(created_at__gte=since)
        
        stats = {
            'total_interactions': logs.count(),
            'messages_received': logs.filter(message_type='RECEIVED').count(),
            'messages_sent': logs.filter(message_type='SENT').count(),
            'unique_users': logs.values('user').distinct().count(),
            'period_days': days
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['post'])
    def clear(self, request):
        """Limpar logs de interação (com filtros opcionais)."""
        user_id = request.data.get('user_id')
        days = request.data.get('days')
        
        queryset = self.queryset
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        if days:
            cutoff = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(created_at__lt=cutoff)
        
        count = queryset.delete()[0]
        
        return Response({
            'message': f'{count} log(s) de interação deletado(s) com sucesso',
            'count': count
        })


class BotStatusViewSet(viewsets.ViewSet):
    """
    ViewSet para monitoramento do status do bot.
    """
    permission_classes = [AllowAny]
    
    def list(self, request):
        """Obter status atual do bot."""
        monitor = BotHealthMonitor()
        current_status = monitor.check_bot_status()
        metrics = monitor.get_metrics_summary(hours=24)
        
        response_data = {
            **current_status,
            **metrics
        }
        
        serializer = BotStatusSerializer(data=response_data)
        serializer.is_valid()
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def test(self, request):
        """Testar bot agora."""
        monitor = BotHealthMonitor()
        result = monitor.test_bot_now()
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Histórico de verificações de saúde."""
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timedelta(hours=hours)
        
        checks = BotHealthCheck.objects.filter(created_at__gte=since)
        serializer = BotHealthCheckSerializer(checks, many=True)
        
        return Response({
            'checks': serializer.data,
            'period_hours': hours
        })
    
    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Métricas detalhadas do bot."""
        monitor = BotHealthMonitor()
        
        # Métricas de diferentes períodos
        metrics_1h = monitor.get_metrics_summary(hours=1)
        metrics_24h = monitor.get_metrics_summary(hours=24)
        metrics_7d = monitor.get_metrics_summary(hours=24*7)
        
        return Response({
            'last_hour': metrics_1h,
            'last_24_hours': metrics_24h,
            'last_7_days': metrics_7d
        })


class BotConfigurationViewSet(viewsets.ModelViewSet):
    """Permite configurar credenciais do WAHA e login do dashboard."""

    queryset = BotConfiguration.objects.all().order_by("-created_at")
    serializer_class = BotConfigurationSerializer
    permission_classes = [AllowAny]  # TODO: proteger com autenticação no futuro

    def create(self, request, *args, **kwargs):
        BotConfiguration.objects.all().delete()
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        instance = serializer.save()
        self._ensure_admin_user(instance)

    def _ensure_admin_user(self, config: BotConfiguration) -> None:
        """Garante que o usuário admin do Django esteja alinhado com a configuração."""

        User = get_user_model()
        admin_user, _ = User.objects.get_or_create(
            username=config.admin_username,
            defaults={"is_staff": True, "is_superuser": True},
        )
        admin_user.is_staff = True
        admin_user.is_superuser = True
        if config.admin_password:
            admin_user.set_password(config.admin_password)
        admin_user.save()

    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request):
        """Retorna a configuração mais recente ou valores padrão."""

        instance = BotConfiguration.objects.order_by("-created_at").first()
        if not instance:
            defaults = BotConfiguration.defaults()  # valores default do ambiente/modelo
            serializer = self.get_serializer(defaults)
        else:
            serializer = self.get_serializer(instance)

        return Response(serializer.data)
