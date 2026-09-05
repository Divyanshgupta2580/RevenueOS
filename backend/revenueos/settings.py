"""Django settings for RevenueOS project."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")

# ------------------------------------------------------------------------------
# Core Settings
# ------------------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "revenueos-insecure-dev-key-change-in-production-minimum-50-characters-long",
)

def _resolve_debug_mode(env: dict[str, str] | None = None) -> tuple[str, bool]:
    """Resolve active environment name and DEBUG mode with strict production defaults.

    Resolution Priority:
    1. Explicit DJANGO_DEBUG or DEBUG boolean flag:
       If explicitly set to 'false', '0', 'no', 'off', 'f', False -> DEBUG is False.
       If explicitly set to 'true', '1', 'yes', 'on', 't', True -> DEBUG is True.
    2. Cloud platform detection:
       If RENDER='true' or RENDER_EXTERNAL_HOSTNAME is present -> default environment is 'production' and DEBUG is False.
    3. Explicit ENVIRONMENT variable:
       If ENVIRONMENT in ('production', 'prod', 'staging') -> DEBUG is False.
       If ENVIRONMENT in ('development', 'dev', 'local', 'test') -> DEBUG is True (unless explicit DJANGO_DEBUG/DEBUG overrides it).
    4. Default fallback:
       In local dev (no cloud platform, no production env), default to ENVIRONMENT='development', DEBUG=True.
    """
    source = env if env is not None else os.environ

    # 1. Cloud platform detection (Render sets RENDER=true or RENDER_EXTERNAL_HOSTNAME)
    is_render = bool(source.get("RENDER") or source.get("RENDER_EXTERNAL_HOSTNAME"))

    # 2. Determine environment name
    default_env = "production" if is_render else "development"
    env_name = source.get("ENVIRONMENT", default_env).strip().lower()

    # 3. Explicit DJANGO_DEBUG or DEBUG flags have highest priority
    raw_debug = source.get("DJANGO_DEBUG")
    if raw_debug is None:
        raw_debug = source.get("DEBUG")

    if raw_debug is not None:
        clean_debug = raw_debug.strip().lower()
        is_debug = clean_debug in ("true", "1", "yes", "on", "t")
    else:
        # Fallback based on environment name and cloud detection
        if is_render or env_name in ("production", "prod", "staging"):
            is_debug = False
        else:
            is_debug = env_name in ("development", "dev", "local", "test")

    return env_name, is_debug


ENVIRONMENT, DEBUG = _resolve_debug_mode()

def _resolve_allowed_hosts(env: dict[str, str] | None = None) -> list[str]:
    """Dynamically construct ALLOWED_HOSTS for local development and cloud deployments (e.g. Render).

    - Preserves standard local development hosts (localhost, 127.0.0.1, 0.0.0.0, testserver, ::1).
    - Incorporates explicit hosts from DJANGO_ALLOWED_HOSTS or ALLOWED_HOSTS.
    - Automatically incorporates Render's injected RENDER_EXTERNAL_HOSTNAME without hardcoding.
    - Strips whitespace, ignores empty entries, prevents duplicates, and strictly forbids wildcards.
    """
    import os

    source = env if env is not None else os.environ

    # 1. Base local development and test hostnames
    default_dev_hosts = ["localhost", "127.0.0.1", "0.0.0.0", "testserver", "::1", "[::1]"]
    hosts: list[str] = list(default_dev_hosts)

    # 2. Gather user/environment-configured host strings
    raw_env_hosts = source.get("DJANGO_ALLOWED_HOSTS") or source.get("ALLOWED_HOSTS") or ""
    if raw_env_hosts.strip():
        for item in raw_env_hosts.split(","):
            cleaned = item.strip()
            # Do not allow wildcard '*' to weaken host protection
            if cleaned and cleaned != "*" and cleaned not in hosts:
                hosts.append(cleaned)

    # 3. Dynamic Render environment detection:
    # Render automatically injects RENDER_EXTERNAL_HOSTNAME (e.g. revenueos-backend-f81a.onrender.com)
    render_hostname = source.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render_hostname and render_hostname != "*":
        clean_render_host = render_hostname.split(":")[0].strip()
        if clean_render_host and clean_render_host not in hosts:
            hosts.append(clean_render_host)

    # 4. Optional Render URL detection (e.g. https://revenueos-backend-f81a.onrender.com)
    render_url = source.get("RENDER_EXTERNAL_URL", "").strip()
    if render_url:
        try:
            from urllib.parse import urlparse

            url_host = urlparse(render_url).hostname
            if url_host and url_host != "*" and url_host not in hosts:
                hosts.append(url_host)
        except Exception:
            pass

    return hosts


ALLOWED_HOSTS = _resolve_allowed_hosts()

# ------------------------------------------------------------------------------
# Application Definition
# ------------------------------------------------------------------------------
INSTALLED_APPS = [
    "daphne",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "channels",
    # RevenueOS Core Applications
    "apps.core",
    "apps.authentication",
    "apps.database",
    "apps.radar",
    "apps.brain",
    "apps.policy",
    "apps.razorpay_adapter",
    "apps.webhooks",
    "apps.websocket",
    "apps.metrics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "revenueos.urls"

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

WSGI_APPLICATION = "revenueos.wsgi.application"
ASGI_APPLICATION = "revenueos.asgi.application"

# ------------------------------------------------------------------------------
# Channels Configuration (In-Memory Channel Layer for Free-Tier Deployment)
# ------------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# ------------------------------------------------------------------------------
# Database: PyMongo Direct (No Django ORM for MongoDB)
# SQLite used only for Django's internal session/auth tables if needed
# ------------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.environ.get("MONGODB_DB", "revenueos")

# ------------------------------------------------------------------------------
# Security, Cookies & Origins
# ------------------------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
WS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "WS_ALLOWED_ORIGINS",
        f"{FRONTEND_ORIGIN},http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

# Automatically include Render external origin in CSRF_TRUSTED_ORIGINS if deployed on Render
_render_host_origin = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if _render_host_origin:
    _clean_host = _render_host_origin.split(":")[0].strip()
    if _clean_host:
        _render_origin = f"https://{_clean_host}"
        if _render_origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_render_origin)

# Ensure frontend and trusted origin hosts are permitted in ALLOWED_HOSTS for Channels origin validation
for _origin in [FRONTEND_ORIGIN] + CSRF_TRUSTED_ORIGINS + WS_ALLOWED_ORIGINS:
    try:
        from urllib.parse import urlparse

        _p_host = urlparse(_origin).hostname
        if _p_host and _p_host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_p_host)
    except Exception:
        pass

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax" if DEBUG else "None"
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_AGE = 86400 * 7  # 7 days

CSRF_COOKIE_HTTPONLY = False  # Allows client to read token for POST requests
CSRF_COOKIE_SAMESITE = "Lax" if DEBUG else "None"
CSRF_COOKIE_SECURE = not DEBUG

# ------------------------------------------------------------------------------
# Third-Party Integrations
# ------------------------------------------------------------------------------
# Cloudflare Turnstile
TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "")
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "")

# Google Gemini API (Multi-Key Failover Support)
GEMINI_API_KEY_1 = os.environ.get("GEMINI_API_KEY_1", "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_API_KEY_2 = os.environ.get("GEMINI_API_KEY_2", "").strip()
GEMINI_API_KEY_3 = os.environ.get("GEMINI_API_KEY_3", "").strip()
GEMINI_API_KEY = GEMINI_API_KEY_1  # Backward compatibility alias
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

# Razorpay Test Mode
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")

# ------------------------------------------------------------------------------
# Internationalization
# ------------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO" if not DEBUG else "DEBUG",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "revenueos": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}
