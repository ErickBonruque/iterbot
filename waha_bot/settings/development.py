# waha_bot/settings/development.py
# Settings de desenvolvimento — herda de base.py e sobrescreve para dev.
# Importa logging.py para garantir que structlog.configure() seja chamado.
from .base import *  # noqa: F403
from .logging import *  # noqa: F403

DEBUG = True

WHITENOISE_AUTOREFRESH = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "iterbot-dev-cache",
        "KEY_PREFIX": "iterbot",
    }
}
