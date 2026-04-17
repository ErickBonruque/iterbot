from pathlib import Path

import dj_database_url
import structlog
from django.core.exceptions import ImproperlyConfigured
from django.templatetags.static import static
from django.urls import reverse_lazy

from config.env import settings

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = settings.django.secret_key

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = settings.django.debug

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

if not DEBUG and (not PORTAL_BASE_URL or not PORTAL_BASE_URL.startswith(("http://", "https://"))):
    raise ImproperlyConfigured(
        "PORTAL_BASE_URL must be set with http:// or https:// when DEBUG=False"
    )

# Email Configuration (dev usa console, prod usa SES via AWS)
if settings.aws.access_key_id and settings.aws.secret_access_key:
    # Use AWS SES when AWS credentials are available
    EMAIL_BACKEND = "django_ses.SESBackend"
    AWS_SES_REGION_NAME = settings.aws.default_region
    AWS_ACCESS_KEY_ID = settings.aws.access_key_id
    AWS_SECRET_ACCESS_KEY = settings.aws.secret_access_key
else:
    # Fallback to console (dev) or SMTP (prod with SMTP credentials)
    EMAIL_BACKEND = settings.email.backend
    EMAIL_HOST = settings.email.host
    EMAIL_PORT = settings.email.port
    EMAIL_USE_TLS = settings.email.use_tls
    EMAIL_HOST_USER = settings.email.user
    EMAIL_HOST_PASSWORD = settings.email.password

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
WHITENOISE_AUTOREFRESH = DEBUG

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

# Cache (LocMem em desenvolvimento/tests, Redis em produção)
if DEBUG:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "iterbot-dev-cache",
            "KEY_PREFIX": "iterbot",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": settings.redis.url,
            "KEY_PREFIX": "iterbot",
        }
    }

# Celery Configuration
CELERY_BROKER_URL = settings.redis.url
CELERY_RESULT_BACKEND = settings.redis.url
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Celery Beat Schedule - envio semanal de review de vagas
# Roda toda segunda-feira as 08:00 horario de Brasilia (CELERY_TIMEZONE = "America/Sao_Paulo")
from celery.schedules import crontab

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

# Security Settings
if not DEBUG:
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

# Structured Logging with structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

UNFOLD = {
    "SITE_TITLE": "IterBot Admin",
    "SITE_HEADER": "IterBot UTFPR",
    "SITE_URL": "/",
    "SITE_LOGO": {
        "light": lambda request: static("img/admin/iterbot-logo-light.svg"),
        "dark": lambda request: static("img/admin/iterbot-logo-dark.svg"),
    },
    "SITE_ICON": {
        "light": lambda request: static("img/admin/iterbot-icon-light.svg"),
        "dark": lambda request: static("img/admin/iterbot-icon-dark.svg"),
    },
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
        "show_all_applications": True,
        "navigation": [
            {
                "title": "Usuarios",
                "separator": False,
                "items": [
                    {
                        "title": "Usuarios Django",
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
                "title": "Bot",
                "separator": False,
                "items": [
                    {
                        "title": "Configuracoes",
                        "icon": "settings",
                        "link": reverse_lazy("admin:bot_botconfiguration_changelist"),
                    },
                    {
                        "title": "Saude do Bot",
                        "icon": "monitor_heart",
                        "link": reverse_lazy("admin:bot_bothealthcheck_changelist"),
                    },
                    {
                        "title": "Metricas",
                        "icon": "bar_chart",
                        "link": reverse_lazy("admin:bot_botmetrics_changelist"),
                    },
                    {
                        "title": "Interacoes",
                        "icon": "chat",
                        "link": reverse_lazy("admin:bot_interactionlog_changelist"),
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
                "title": "Links Rapidos",
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

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}
