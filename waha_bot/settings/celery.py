# waha_bot/settings/celery.py
# Módulo folha — NÃO herda de base.py (evita import circular).
# Importado por base.py via `from .celery import *`.
from celery.schedules import crontab

from config.env import settings

# Celery Configuration
CELERY_BROKER_URL = settings.redis.url
CELERY_RESULT_BACKEND = settings.redis.url
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
# String literal — não referenciar TIME_ZONE de base.py para evitar dependência circular
CELERY_TIMEZONE = "America/Sao_Paulo"

# Celery Beat Schedule - envio semanal de review de vagas
# Roda toda segunda-feira as 08:00 horario de Brasilia (CELERY_TIMEZONE = "America/Sao_Paulo")
CELERY_BEAT_SCHEDULE = {
    # Envio semanal de review de vagas — toda segunda-feira às 08:00 (Brasília)
    "send-weekly-job-review": {
        "task": "apps.jobs.tasks.send_weekly_job_review",
        "schedule": crontab(hour=8, minute=0, day_of_week="monday"),
    },
    # Health check da sessão WAHA — a cada 5 minutos (STAB-01)
    "check-waha-health": {
        "task": "apps.bot.tasks.check_waha_health",
        "schedule": crontab(minute="*/5"),
    },
    # Limpeza de registros BotHealthCheck antigos — todo domingo às 02:00
    "clean-old-health-checks": {
        "task": "apps.bot.tasks.clean_old_health_checks",
        "schedule": crontab(hour=2, minute=0, day_of_week="sunday"),
    },
}
