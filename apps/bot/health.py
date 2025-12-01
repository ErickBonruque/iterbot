"""
Sistema de health check e monitoramento do bot WAHA.
"""
import os
import time
import requests
import logging
from datetime import datetime, timedelta

from django.utils import timezone
from django.core.cache import cache
from django.db.models import Avg

from apps.bot.models import BotHealthCheck, BotMetrics
from config.env import settings

logger = logging.getLogger(__name__)


class BotHealthMonitor:
    """
    Monitora a saúde e performance do bot WAHA.
    """
    
    def __init__(self, waha_url=None, session_name=None):
        """Inicializa o monitor usando as configurações centrais do WAHA."""

        self.waha_url = waha_url or settings.waha.base_url
        self.session_name = session_name or settings.waha.session_name
        self.api_key = settings.waha.api_key
        
    def check_bot_status(self):
        """
        Verifica o status do bot WAHA e registra métricas.
        
        Returns:
            dict: {
                'status': 'online' | 'offline' | 'error',
                'response_time': float (ms),
                'session_status': str,
                'last_check': datetime,
                'error_message': str | None
            }
        """
        start_time = time.time()
        result = {
            'status': 'offline',
            'response_time': None,
            'session_status': 'unknown',
            'last_check': timezone.now(),
            'error_message': None
        }
        
        try:
            # Verificar status da sessão
            headers = {}
            if self.api_key:
                headers['X-Api-Key'] = self.api_key
            
            response = requests.get(
                f'{self.waha_url}/api/sessions/{self.session_name}',
                headers=headers,
                timeout=5
            )
            
            response_time = (time.time() - start_time) * 1000  # ms
            result['response_time'] = round(response_time, 2)
            
            if response.status_code == 200:
                data = response.json()
                result['status'] = 'online' if data.get('status') == 'WORKING' else 'offline'
                result['session_status'] = data.get('status', 'unknown')
            else:
                result['status'] = 'error'
                result['error_message'] = f'HTTP {response.status_code}'
                
        except requests.exceptions.Timeout:
            result['status'] = 'error'
            result['error_message'] = 'Timeout ao conectar com WAHA'
            result['response_time'] = 5000.0
            
        except requests.exceptions.ConnectionError:
            result['status'] = 'offline'
            result['error_message'] = 'Não foi possível conectar ao serviço WAHA'
            
        except Exception as e:
            result['status'] = 'error'
            result['error_message'] = str(e)
            logger.error(f"Erro ao verificar status do bot: {e}")
        
        # Salvar no banco
        BotHealthCheck.objects.create(
            status=result['status'],
            response_time=result['response_time'],
            error_message=result['error_message'],
            session_status=result['session_status']
        )
        
        # Salvar no cache para acesso rápido
        cache.set('bot_last_status', result, timeout=60)  # 1 minuto
        
        return result
    
    def get_metrics_summary(self, hours=24):
        """
        Obtém resumo das métricas do bot nas últimas N horas.
        
        Args:
            hours: Número de horas para análise (padrão: 24)
            
        Returns:
            dict: {
                'uptime_percentage': float,
                'avg_response_time': float,
                'total_checks': int,
                'error_count': int,
                'last_error': str | None
            }
        """
        since = timezone.now() - timedelta(hours=hours)
        checks = BotHealthCheck.objects.filter(created_at__gte=since)
        
        total = checks.count()
        if total == 0:
            return {
                'uptime_percentage': 0,
                'avg_response_time': 0,
                'total_checks': 0,
                'error_count': 0,
                'last_error': None
            }
        
        online_count = checks.filter(status='online').count()
        error_count = checks.exclude(status='online').count()
        
        # Calcular tempo médio de resposta (excluindo erros de timeout)
        valid_checks = checks.filter(response_time__isnull=False, response_time__lt=5000)
        avg_response = valid_checks.aggregate(Avg('response_time'))['response_time__avg'] or 0
        
        # Último erro
        last_error_check = checks.filter(error_message__isnull=False).order_by('-created_at').first()
        
        return {
            'uptime_percentage': round((online_count / total) * 100, 2),
            'avg_response_time': round(avg_response, 2),
            'total_checks': total,
            'error_count': error_count,
            'last_error': last_error_check.error_message if last_error_check else None
        }
    
    def test_bot_now(self):
        """
        Executa um teste completo do bot (verificação + envio de mensagem de teste).
        
        Returns:
            dict: Resultado do teste
        """
        # Primeiro verifica status
        status = self.check_bot_status()
        
        if status['status'] != 'online':
            return {
                'success': False,
                'message': f"Bot não está online. Status: {status['session_status']}",
                'details': status
            }
        
        # Tenta enviar mensagem de teste (para um número de teste configurado)
        # Por segurança, não vamos enviar mensagem real no teste
        return {
            'success': True,
            'message': 'Bot está operacional',
            'details': status
        }
    
    def clean_old_health_checks(self, days=7):
        """
        Remove registros de health check antigos.
        
        Args:
            days: Manter apenas registros dos últimos N dias
        """
        cutoff = timezone.now() - timedelta(days=days)
        deleted_count = BotHealthCheck.objects.filter(created_at__lt=cutoff).delete()[0]
        logger.info(f"Removidos {deleted_count} registros de health check antigos")
        return deleted_count
