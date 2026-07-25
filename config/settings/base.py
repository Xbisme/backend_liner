"""Base settings — every value is env-driven (Constitution Principle VI)."""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# --- Core --------------------------------------------------------------------
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="insecure-dev-key-change-me-0000000000000000000000000000",
)
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# App-level gate (Layer-1 auth). Empty → middleware fails closed.
X_APP_KEY = env("X_APP_KEY", default="")
APP_KEY_EXEMPT_PREFIXES = env.list(
    "APP_KEY_EXEMPT_PREFIXES", default=["/admin", "/static", "/health"]
)

# --- Applications ------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "apps.accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "core.middleware.AppKeyMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

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

# --- Database ----------------------------------------------------------------
# PostgreSQL in real environments; sqlite default keeps dev/test runnable.
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}

# --- Cache -------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# --- Auth --------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

# Argon2id first (Constitution Principle I/II); PBKDF2 kept as fallback.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation." "MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
]

# --- DRF ---------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("core.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "core.pagination.CursorPage",
    "PAGE_SIZE": env.int("DEFAULT_PAGE_SIZE", default=20),
    "UNAUTHENTICATED_USER": None,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("ACCESS_TOKEN_LIFETIME_MINUTES", default=30)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("REFRESH_TOKEN_LIFETIME_DAYS", default=30)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# --- Social providers --------------------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
APPLE_CLIENT_ID = env("APPLE_CLIENT_ID", default="")
APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"

# --- i18n / static -----------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Logging (structured; secrets redacted — Principle IX) -------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_secrets": {"()": "core.logging.SensitiveDataFilter"},
    },
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "filters": ["redact_secrets"],
        },
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
