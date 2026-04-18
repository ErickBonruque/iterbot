# waha_bot/settings/production.py
# Settings de produção — herda de base.py e aplica security + logging.
# CRÍTICO: from .security import * deve vir APÓS from .base import *
# para que os overrides de security sejam aplicados sobre o namespace de base.
from django.core.exceptions import ImproperlyConfigured

from config.env import settings

from .base import *  # noqa: F401, F403
from .logging import *  # noqa: F401, F403
from .security import *  # noqa: F401, F403

DEBUG = False

# Validação de PORTAL_BASE_URL em produção (runtime check — DEBUG sempre False aqui)
if not PORTAL_BASE_URL or not PORTAL_BASE_URL.startswith(("http://", "https://")):  # noqa: F821
    raise ImproperlyConfigured(
        "PORTAL_BASE_URL must be set with http:// or https:// when DEBUG=False"
    )

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": settings.redis.url,
        "KEY_PREFIX": "iterbot",
    }
}
