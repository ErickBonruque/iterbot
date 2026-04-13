"""Celery app bootstrap for Django startup."""

# Garante que o app Celery e suas tasks sejam carregados quando Django inicia.
from .celery import app as celery_app

__all__ = ("celery_app",)
