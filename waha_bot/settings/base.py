from pathlib import Path

import dj_database_url
from django.templatetags.static import static
from django.urls import reverse_lazy

from config.env import settings

from .celery import *  # noqa: F403

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# __file__ = waha_bot/settings/base.py
# .parent   = waha_bot/settings/
# .parent.parent = waha_bot/
# .parent.parent.parent = raiz do projeto  ← CORRETO
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = settings.django.secret_key

# Chave dedicada para criptografia de campos sensíveis (EncryptedCharField).
# Configure via Docker secret "encryption_key" ou variável de ambiente ENCRYPTION_KEY.
# Se ausente, infra/security/encryption.py usa derivação de SECRET_KEY como fallback.
ENCRYPTION_KEY = settings.django.encryption_key

# Default seguro — cada ambiente sobrescreve (development.py: True, production.py: False)
DEBUG = False

ALLOWED_HOSTS = settings.django.allowed_hosts


# Application definition

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third Party Apps
    "rest_framework",
    "django_filters",
    "allauth",
    "allauth.account",
    "django_ses",
    # Local Apps
    "apps.core",
    "apps.users",
    "apps.courses",
    "apps.jobs",
    "apps.bot",
    "apps.companies",
]

SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "infra.middleware.correlation_id.CorrelationIdMiddleware",
    "infra.middleware.structured_logging.StructuredLoggingMiddleware",
]

ROOT_URLCONF = "waha_bot.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "waha_bot.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": dj_database_url.parse(
        settings.database.url,
        conn_max_age=600,
        conn_health_checks=True,
    )
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# django-allauth Configuration
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_ADAPTER = "apps.users.adapters.UTFPRAccountAdapter"
LOGIN_REDIRECT_URL = "/accounts/success/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/accounts/login/"
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = "/accounts/email-confirmed/"

# Portal de Empresas (usado pelo bot para enviar links)
PORTAL_BASE_URL = settings.django.portal_base_url

# Email Configuration
# ---------------------------------------------------------------------------
# Toda a entrega transacional real passa por `infra/email/factory.py`, roteada
# pelo `EMAIL_PROVIDER` (Brevo por padrao). O adapter do allauth
# (`apps/users/adapters.py`) intercepta 100% dos e-mails do allauth e usa o
# mesmo factory — ou seja, Django `EMAIL_BACKEND` abaixo raramente e atingido.
#
# Mantemos `EMAIL_BACKEND` configuravel para cenarios de fallback (ex.:
# `mail_admins`, `send_mail` direto em futuros codigos). O valor vem do env
# `EMAIL_BACKEND`, default console.
#
# Se `EMAIL_PROVIDER=ses` for usado explicitamente, o factory usa o backend
# Django (DjangoSendMailProvider); nesse caso configure
# `EMAIL_BACKEND=django_ses.SESBackend` no .env explicitamente.
EMAIL_BACKEND = settings.email.backend
EMAIL_HOST = settings.email.host
EMAIL_PORT = settings.email.port
EMAIL_USE_TLS = settings.email.use_tls
EMAIL_HOST_USER = settings.email.user
EMAIL_HOST_PASSWORD = settings.email.password

# Se o operador configurou EMAIL_BACKEND=django_ses.SESBackend, populamos as
# credenciais que o django-ses espera (caminho opcional, nao e o default).
if EMAIL_BACKEND == "django_ses.SESBackend":
    AWS_SES_REGION_NAME = settings.aws.default_region
    AWS_ACCESS_KEY_ID = settings.aws.access_key_id
    AWS_SECRET_ACCESS_KEY = settings.aws.secret_access_key

DEFAULT_FROM_EMAIL = settings.email.from_email


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "pt-br"

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
# Default seguro (False); development.py sobrescreve para True
WHITENOISE_AUTOREFRESH = False

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

UNFOLD = {
    "SITE_TITLE": "IterBot Admin",
    "SITE_HEADER": "IterBot UTFPR",
    "SITE_URL": "/",
    "SITE_LOGO": lambda request: static("img/logo-utfpr.png"),
    "SITE_ICON": lambda request: static("img/logo-icon.png"),
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "SEARCH_MODELS": ["auth.User", "jobs.Company", "jobs.Job"],
    "COLORS": {
        "primary": {
            "50": "255 252 224",
            "100": "255 248 179",
            "200": "255 240 102",
            "300": "255 232 26",
            "400": "255 220 0",
            "500": "255 209 0",
            "600": "230 188 0",
            "700": "204 167 0",
            "800": "179 146 0",
            "900": "153 125 0",
            "950": "102 83 0",
        },
    },
    "STYLES": [
        lambda request: static("css/admin_custom.css"),
    ],
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Painel",
                "separator": False,
                "items": [
                    {
                        "title": "Painel Principal",
                        "icon": "home",
                        "link": "/admin/",
                    },
                ],
            },
            {
                "title": "Monitoramento",
                "separator": False,
                "items": [
                    {
                        "title": "Status do Bot",
                        "icon": "monitor_heart",
                        "link": "/admin/status-bot/",
                    },
                    {
                        "title": "Observabilidade",
                        "icon": "troubleshoot",
                        "link": "/admin/observabilidade/",
                    },
                    {
                        "title": "Métricas de Negócio",
                        "icon": "bar_chart",
                        "link": "/admin/metricas-negocio/",
                    },
                    {
                        "title": "Métricas Técnicas",
                        "icon": "speed",
                        "link": "/admin/metricas-tecnicas/",
                    },
                ],
            },
            {
                "title": "Usuários",
                "separator": False,
                "items": [
                    {
                        "title": "Usuários Django",
                        "icon": "person",
                        "link": reverse_lazy("admin:auth_user_changelist"),
                    },
                    {
                        "title": "Perfis de Alunos",
                        "icon": "school",
                        "link": reverse_lazy("admin:users_userprofile_changelist"),
                    },
                ],
            },
            {
                "title": "Empresas e Vagas",
                "separator": False,
                "items": [
                    {
                        "title": "Empresas",
                        "icon": "business",
                        "link": reverse_lazy("admin:jobs_company_changelist"),
                    },
                    {
                        "title": "Vagas",
                        "icon": "work",
                        "link": reverse_lazy("admin:jobs_job_changelist"),
                    },
                    {
                        "title": "Candidaturas",
                        "icon": "article",
                        "link": reverse_lazy("admin:jobs_jobapplication_changelist"),
                    },
                ],
            },
            {
                "title": "Bot WhatsApp",
                "separator": False,
                "items": [
                    {
                        "title": "Logs de Saúde",
                        "icon": "favorite",
                        "link": reverse_lazy("admin:bot_bothealthcheck_changelist"),
                    },
                    {
                        "title": "Log de Ações",
                        "icon": "receipt_long",
                        "link": reverse_lazy("admin:bot_botactionlog_changelist"),
                    },
                    {
                        "title": "Interações",
                        "icon": "chat",
                        "link": reverse_lazy("admin:bot_interactionlog_changelist"),
                    },
                    {
                        "title": "Métricas Brutas",
                        "icon": "data_object",
                        "link": reverse_lazy("admin:bot_botmetrics_changelist"),
                    },
                ],
            },
            {
                "title": "Cursos",
                "separator": False,
                "items": [
                    {
                        "title": "Cursos",
                        "icon": "menu_book",
                        "link": reverse_lazy("admin:courses_course_changelist"),
                    },
                    {
                        "title": "Termos de Busca",
                        "icon": "manage_search",
                        "link": reverse_lazy("admin:courses_searchterm_changelist"),
                    },
                ],
            },
            {
                "title": "Links Rápidos",
                "separator": False,
                "items": [
                    {
                        "title": "GitHub",
                        "icon": "open_in_new",
                        "link": "https://github.com/ErickBonruque/IterBot-UTFPR",
                    },
                ],
            },
        ],
    },
}

# Custom Admin Site
ADMIN_SITE = "apps.core.admin.iterbot_admin"
