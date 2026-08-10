"""
WhatsAppBusinessAI — Base Django Settings
Shared across all environments. Environment-specific overrides live in
development.py / production.py.
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
env_file = BASE_DIR.parent / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

# ── Security ──────────────────────────────────────────────────
SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# ── Applications ──────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "django_celery_beat",
    "django_celery_results",
    "drf_spectacular",
]

# Only apps with real code this phase are registered. The remaining domain
# apps under backend/apps/ exist as directory placeholders (see docs/ROADMAP.md)
# and are added here as each phase implements them.
LOCAL_APPS = [
    "core",
    "apps.tenants",
    "apps.businesses",
    "apps.accounts",
    "apps.common",
    "apps.customers",
    "apps.conversations",
    "apps.messages",
    "apps.whatsapp",
    "apps.products",
    "apps.orders",
    "apps.ai",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ── Middleware ────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.TenantMiddleware",
    "core.middleware.RequestLoggingMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ── Database ──────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="whatsapp_business_ai"),
        "USER": env("POSTGRES_USER", default="waba_user"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="waba_pass"),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"connect_timeout": 10},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Cache (Redis) ─────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
        },
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# ── Authentication ────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── REST Framework ────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardResultsPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
    "NON_FIELD_ERRORS_KEY": "non_field_errors",
}

# ── JWT ───────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=60)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env("JWT_SIGNING_KEY", default=SECRET_KEY),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
}

# ── CORS / CSRF ───────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-tenant-id",
]
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["http://localhost:3000"])

# ── Celery ────────────────────────────────────────────────────
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = env("CELERY_TIMEZONE", default="Africa/Nairobi")
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# Explicit per Celery 6.0's deprecation of the old broker_connection_retry
# default — we do want startup retries (e.g. broker briefly unreachable
# while Docker Desktop is still warming up).
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_ROUTES = {
    "apps.whatsapp.tasks.*": {"queue": "high_priority"},
    "apps.ai.tasks.*": {"queue": "default"},
    # More routes added as background-processing-heavy apps (knowledge,
    # campaigns) land in later phases.
}

# ── Internationalization ──────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="Africa/Nairobi")
USE_I18N = True
USE_TZ = True

# ── Static & Media Files ──────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ── File Upload ───────────────────────────────────────────────
MAX_UPLOAD_SIZE = env.int("MAX_UPLOAD_SIZE_MB", default=20) * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE

# ── Email ─────────────────────────────────────────────────────
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="WABA AI <noreply@wabaai.local>")

# ── AI Provider Abstraction ────────────────────────────────────
# Real usage lands in apps.ai (Phase 8). Keys are read here so .env is the
# single source of config from day one, per the AI-provider-agnostic design.
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
DEFAULT_AI_PROVIDER = env("DEFAULT_AI_PROVIDER", default="openai")

# ── WhatsApp Cloud API (apps.whatsapp) ──────────────────────────
# Per-business credentials (phone_number_id, access_token, ...) live
# encrypted in apps.whatsapp.WhatsAppAccount, NOT here — a business
# connects its own number via the API. What IS platform-level (configured
# once, in your Meta App dashboard, shared by every business's webhook
# traffic under that App):
WHATSAPP_VERIFY_TOKEN = env("WHATSAPP_VERIFY_TOKEN", default="")
WHATSAPP_APP_SECRET = env("WHATSAPP_APP_SECRET", default="")
WHATSAPP_GRAPH_API_BASE_URL = env(
    "WHATSAPP_GRAPH_API_BASE_URL", default="https://graph.facebook.com/v21.0"
)
# Fernet key encrypting WhatsAppAccount.access_token at rest — generate
# with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
WHATSAPP_TOKEN_ENCRYPTION_KEY = env("WHATSAPP_TOKEN_ENCRYPTION_KEY", default="")

# ── Object Storage (optional — local disk by default) ──────────
USE_S3 = env.bool("USE_S3", default=False)
if USE_S3:
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    AWS_ACCESS_KEY_ID = env("STORAGE_ACCESS_KEY", default="")
    AWS_SECRET_ACCESS_KEY = env("STORAGE_SECRET_KEY", default="")
    AWS_STORAGE_BUCKET_NAME = env("STORAGE_BUCKET", default="")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="us-east-1")
    AWS_DEFAULT_ACL = None

# ── API Documentation ─────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "WABA AI — WhatsApp Business AI Platform API",
    "DESCRIPTION": "Multi-Tenant WhatsApp Business AI SaaS Platform — REST API Documentation",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    "TAGS": [
        {"name": "auth", "description": "Authentication"},
        {
            "name": "tenants",
            "description": "Platform tenant & plan management (super admin)",
        },
        {"name": "businesses", "description": "Business profile management"},
        {"name": "staff", "description": "Staff/manager account management within a tenant"},
        {"name": "customers", "description": "Customer CRM"},
        {"name": "conversations", "description": "Conversations & staff assignment"},
        {"name": "messaging", "description": "Messages & attachments"},
        {"name": "whatsapp", "description": "WhatsApp account connection & webhook"},
        {"name": "products", "description": "Product catalog"},
        {"name": "orders", "description": "Customer orders"},
        {"name": "ai", "description": "AI assistant configuration & testing"},
    ],
}

# ── Platform ──────────────────────────────────────────────────
PLATFORM_NAME = env("PLATFORM_NAME", default="WABA AI")
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")
BACKEND_URL = env("BACKEND_URL", default="http://localhost:8000")

# ── Super Admin seed (used by `manage.py createsuperadmin`) ────
SUPERADMIN_EMAIL = env("SUPERADMIN_EMAIL", default="")
SUPERADMIN_PASSWORD = env("SUPERADMIN_PASSWORD", default="")
SUPERADMIN_FIRST_NAME = env("SUPERADMIN_FIRST_NAME", default="Platform")

# ── Logging ───────────────────────────────────────────────────
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {"format": "{levelname} {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file_info": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "info.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "verbose",
        },
        "file_error": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "error.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "verbose",
        },
        "audit_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "audit.log"),
            "maxBytes": 50 * 1024 * 1024,
            "backupCount": 30,
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console", "file_info", "file_error"], "level": "INFO"},
    "loggers": {
        "django": {
            "handlers": ["console", "file_error"],
            "level": "WARNING",
            "propagate": False,
        },
        "waba": {
            "handlers": ["console", "file_info", "file_error"],
            "level": "DEBUG",
            "propagate": False,
        },
        "audit": {"handlers": ["audit_file"], "level": "INFO", "propagate": False},
        "celery": {
            "handlers": ["console", "file_info"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
