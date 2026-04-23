# waha_bot/settings/security.py
# Módulo folha — NÃO herda de base.py.
# Importado APENAS por production.py. A ausência deste import em
# development.py já serve como guard — nenhuma checagem condicional necessária.
# NUNCA importar este módulo em development.py (SESSION_COOKIE_SECURE e HSTS quebrariam o servidor local).

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# SECURE_SSL_REDIRECT removido — Traefik já redireciona HTTP→HTTPS no entrypoint.
# Django não deve redirecionar: WAHA acessa o webhook via rede interna Docker
# (http://backend:8000/webhook/) sem X-Forwarded-Proto, o que causaria 301
# mesmo com SECURE_REDIRECT_EXEMPT (Django faz lstrip("/") no path antes de
# checar o padrão, então "^/webhook/$" nunca casa com "webhook/").
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
