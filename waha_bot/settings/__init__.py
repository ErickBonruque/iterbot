# waha_bot/settings/__init__.py
# Smart router — roteia imports para development ou production com base em
# DJANGO_SETTINGS_MODULE. Mantém compatibilidade retroativa com entry points
# que usam setdefault("DJANGO_SETTINGS_MODULE", "waha_bot.settings").
import os

_dsm = os.environ.get("DJANGO_SETTINGS_MODULE", "waha_bot.settings")

if _dsm in ("waha_bot.settings", "waha_bot.settings.development"):
    from .development import *  # noqa: F403
elif _dsm == "waha_bot.settings.production":
    from .production import *  # noqa: F403
else:
    # Fallback seguro: development
    from .development import *  # noqa: F403
