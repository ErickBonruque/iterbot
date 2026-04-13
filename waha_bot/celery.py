# waha_bot/celery.py
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "waha_bot.settings")

app = Celery("waha_bot")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
