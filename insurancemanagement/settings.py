"""
Django settings for the Insurance Management System.

All environment-specific / secret values are read from the environment
(optionally via a local ``.env`` file). See ``.env.example`` for the full list.
"""

import warnings
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# WhiteNoise logs a cosmetic warning when STATIC_ROOT has not been populated by
# `collectstatic` yet (e.g. during tests). Files are still served via finders.
warnings.filterwarnings("ignore", message="No directory at", category=UserWarning)

# --- Environment -------------------------------------------------------------
env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["127.0.0.1", "localhost"]),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    DJANGO_SECURE_SSL_REDIRECT=(bool, False),
    CONTACT_RECEIVING_EMAILS=(list, []),
)

# Load .env if present (never committed).
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    env.read_env(str(_env_file))

# --- Core -------------------------------------------------------------------
DEBUG = env("DJANGO_DEBUG")

# A secret key is mandatory in production; a clearly-insecure fallback keeps
# local development friction-free without ever shipping a real key in source.
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default=("django-insecure-dev-only-key-change-me" if DEBUG else ""),
)
if not SECRET_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY is required when DEBUG is False.\n"
        "For local development: copy .env.example to .env and set DJANGO_DEBUG=True "
        "plus a generated DJANGO_SECRET_KEY\n"
        '  python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"\n'
        "For production: set the DJANGO_SECRET_KEY environment variable."
    )

ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "widget_tweaks",
    "insurance",
    "customer",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "insurancemanagement.urls"

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
                "insurance.context_processors.notifications",
            ],
        },
    },
]

WSGI_APPLICATION = "insurancemanagement.wsgi.application"

# --- Database --------------------------------------------------------------
# An empty/blank DATABASE_URL (e.g. a `.env` copied verbatim from the example)
# falls back to local SQLite rather than producing an invalid config.
_database_url = env("DATABASE_URL", default="").strip()
_sqlite_url = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
DATABASES = {"default": environ.Env.db_url_config(_database_url or _sqlite_url)}

# --- Auth -----------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "customerlogin"
LOGIN_REDIRECT_URL = "afterlogin"
LOGOUT_REDIRECT_URL = "home"

# --- Internationalisation ------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static & media ----------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# WhiteNoise serves static files (with compression) when DEBUG is False, so the
# app works without a separate web server. USE_FINDERS lets it serve straight
# from the source dirs, so neither `runserver` nor the test suite needs
# `collectstatic` to have run first (production still runs it - see README).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
WHITENOISE_USE_FINDERS = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Email --------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@example.com")
CONTACT_RECEIVING_EMAILS = env("CONTACT_RECEIVING_EMAILS")

# --- Security (enforced when DEBUG is False) ---------------------------
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # allow JS-driven forms to read the token if needed
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

if not DEBUG:
    SECURE_SSL_REDIRECT = env("DJANGO_SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 days
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Domain-specific defaults
PREMIUM_CALCULATOR_BASE_RATE = 0.02  # fraction of sum assured per year, before factors
