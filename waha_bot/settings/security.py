# waha_bot/settings/security.py
# Módulo folha — NÃO herda de base.py.
# Importado APENAS por production.py. A ausência deste import em
# development.py já serve como guard — nenhuma checagem condicional necessária.
# NUNCA importar este módulo em development.py (SECURE_SSL_REDIRECT=True quebraria o servidor local).

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
# WAHA envia webhook internamente por HTTP na rede Docker
# (WHATSAPP_HOOK_URL=http://backend:8000/webhook/). Sem essa
# exceção, o SecurityMiddleware redireciona POST para HTTPS e o
# webhook não chega ao bot.
SECURE_REDIRECT_EXEMPT = [r"^webhook/$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
