from pathlib import Path

import dj_database_url
import structlog

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
    "jazzmin",
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
PORTAL_BASE_URL = getattr(settings.django, 'portal_base_url', "http://localhost:8000")

# Email Configuration (dev usa console, prod usa variáveis de ambiente)
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

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
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

# Cache (Redis for production, LocMem for development)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": settings.redis.url,
        "KEY_PREFIX": "capyvagas",
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
    SECURE_SSL_REDIRECT = True
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

# django-jazzmin Configuration
JAZZMIN_SETTINGS = {
    "site_title": "CapyVagas Admin",
    "site_header": "CapyVagas",
    "site_brand": "CapyVagas UTFPR",
    "welcome_sign": "Painel Administrativo CapyVagas UTFPR",
    "copyright": "CapyVagas UTFPR",
    "search_model": ["auth.User", "jobs.Company", "jobs.Job"],
    "show_sidebar": True,
    "navigation_expanded": True,
    "order_with_respect_to": [
        "auth",
        "users",
        "users.UserProfile",
        "jobs",
        "jobs.Company",
        "jobs.Job",
        "jobs.JobApplication",
        "bot",
        "bot.BotConfiguration",
        "bot.BotMessage",
        "bot.BotHealthCheck",
        "bot.BotMetrics",
        "bot.InteractionLog",
        "courses",
    ],
    "hide_apps": ["sites"],
    "hide_models": [],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "users.UserProfile": "fas fa-user-graduate",
        "jobs.Company": "fas fa-building",
        "jobs.Job": "fas fa-briefcase",
        "jobs.JobApplication": "fas fa-file-alt",
        "jobs.JobSearchLog": "fas fa-search",
        "bot.BotConfiguration": "fas fa-cog",
        "bot.BotMessage": "fas fa-comment-dots",
        "bot.BotHealthCheck": "fas fa-heartbeat",
        "bot.BotMetrics": "fas fa-chart-bar",
        "bot.InteractionLog": "fas fa-history",
        "courses.Course": "fas fa-graduation-cap",
        "courses.SearchTerm": "fas fa-search",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": False,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "language_chooser": False,
    "custom_css": "css/admin_custom.css",
    "custom_links": {
        "CapyVagas": [
            {
                "name": "GitHub",
                "url": "https://github.com/ErickBonruque/CapyVagas-UTFPR",
                "new_window": True,
                "icon": "fab fa-github",
            },
        ],
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-warning",
    "navbar": "navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-warning",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}

# Custom Admin Site
ADMIN_SITE = 'apps.core.admin.capyvagas_admin'

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
