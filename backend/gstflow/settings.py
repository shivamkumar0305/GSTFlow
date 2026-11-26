"""
Django settings for gstflow project.
"""

import os
import tempfile
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get(
    "SECRET_KEY", "django-insecure-=&3lf8-lg+zykrh*et(pfay5uk0fa^%br*6bitsqh-p$31-3%*"
)

DEBUG = os.environ.get("DEBUG", "True") == "True"


def env_list(name: str, default: str = "") -> list[str]:
    return [value.strip() for value in os.environ.get(name, default).split(",") if value.strip()]


if not DEBUG and (not SECRET_KEY or SECRET_KEY.startswith("django-insecure-")):
    raise ImproperlyConfigured("SECRET_KEY must be set to a strong value when DEBUG=False.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CORS_ALLOWED_ORIGINS = [
    "https://gst-flow-ten.vercel.app",
]

CSRF_TRUSTED_ORIGINS = [
    "https://gst-flow-ten.vercel.app",
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
    "accounts",
    "invoices",
    "reconciliation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "gstflow.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "gstflow.wsgi.application"

DATABASE_OPTIONS = {}
if db_sslmode := os.environ.get("DB_SSLMODE"):
    DATABASE_OPTIONS["sslmode"] = db_sslmode

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "gstflow"),
        "USER": os.environ.get("DB_USER", os.environ.get("USER", "postgres")),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        "OPTIONS": DATABASE_OPTIONS,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF / JWT ---

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_THROTTLE_RATES": {"anon": "30/minute", "user": "240/hour"},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# Uploads are stored in Redis only long enough for the worker to parse them.
MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "10"))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# --- Celery ---
CELERY_TASK_ALWAYS_EAGER = (
    os.environ.get("CELERY_TASK_ALWAYS_EAGER", "True").lower() in ("true", "1", "t")
)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

if CELERY_TASK_ALWAYS_EAGER:
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
else:
    CEvLERY_BROKER_URL = os.environ.get(
        "CELERY_BROKER_URL", os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    )
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
q
# --- Cache configuration ---
# If Redis is configured (via REDIS_CACHE_URL or REDIS_URL), use RedisCache.
# Otherwise, fall back to FileBasedCache so all Gunicorn workers share the cache
# (for DRF rate limiting, encrypted file decryption passwords, and upload buffers)
# without requiring an external Redis service.
REDIS_CACHE = os.environ.get("REDIS_CACHE_URL") or os.environ.get("REDIS_URL")

if REDIS_CACHE:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_CACHE,
        }
    }
else:
    CACHE_DIR = Path(os.environ.get("CACHE_DIR", tempfile.gettempdir())) / "gstflow_cache"
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
    except OSError:
        pass
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": str(CACHE_DIR),
            "OPTIONS": {
                "MAX_ENTRIES": 1000,
            },
        }
    }

UPLOAD_PASSWORD_TTL_SECONDS = 300
UPLOAD_PASSWORD_MAX_ATTEMPTS = 5

# --- AI explanation provider (isolated, swappable — see reconciliation/ai_explain.py) ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
AI_EXPLANATIONS_ENABLED = os.environ.get("AI_EXPLANATIONS_ENABLED", "True") == "True"

# Reconciliation matching tolerance (absolute rupee tolerance on invoice value)
RECONCILIATION_VALUE_TOLERANCE = float(os.environ.get("RECONCILIATION_VALUE_TOLERANCE", "1.0"))

# Reverse-proxy and HTTPS settings. Keep FORCE_HTTPS=False for local development.
FORCE_HTTPS = os.environ.get("FORCE_HTTPS", "False") == "True"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = FORCE_HTTPS
SESSION_COOKIE_SECURE = FORCE_HTTPS
CSRF_COOKIE_SECURE = FORCE_HTTPS
SECURE_HSTS_SECONDS = 31536000 if FORCE_HTTPS else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = FORCE_HTTPS
SECURE_HSTS_PRELOAD = FORCE_HTTPS
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
