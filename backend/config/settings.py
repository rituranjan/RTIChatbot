import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE, override=True)


def env(key: str, default=None, required: bool = False):
    value = os.getenv(key, default)
    if isinstance(value, str):
        value = value.strip().strip('"').strip("'")
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def reload_runtime_env():
    """Re-read the mounted .env so edits apply without rebuilding the image."""
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)

    values = {
        "LLM_PROVIDER": env("LLM_PROVIDER", "ollama").strip().lower(),
        "EMBEDDING_PROVIDER": env("EMBEDDING_PROVIDER", "ollama").strip().lower(),
        "AZURE_ENDPOINT": env("AZURE_ENDPOINT", "").rstrip("/"),
        "AZURE_API_KEY": env("AZURE_API_KEY", "") or env("API_KEY", ""),
        "AZURE_API_VERSION": env("AZURE_API_VERSION", "") or env("API_VERSION", "2025-04-01-preview"),
        "AZURE_CHAT_DEPLOYMENT": (
            env("AZURE_CHAT_DEPLOYMENT", "")
            or env("AZURE_DEPLOYMENT", "")
            or env("MODEL_NAME", "")
        ),
        "AZURE_EMBEDDING_DEPLOYMENT": env("AZURE_EMBEDDING_DEPLOYMENT", "")
        or env("EMBEDDING_MODEL_NAME", ""),
        "OPENAI_API_KEY": env("OPENAI_API_KEY", ""),
        "OPENAI_BASE_URL": env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        "OPENAI_CHAT_MODEL": env("OPENAI_CHAT_MODEL", "") or env("MODEL_NAME", "gpt-4o-mini"),
        "OPENAI_EMBEDDING_MODEL": env("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        "OLLAMA_CHAT_MODEL": env("OLLAMA_CHAT_MODEL", "qwen2.5:3b"),
        "OLLAMA_EMBEDDING_MODEL": env("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        "OLLAMA_VISION_MODEL": env("OLLAMA_VISION_MODEL", ""),
        "OLLAMA_TIMEOUT": int(env("OLLAMA_TIMEOUT", "300")),
        "OLLAMA_CONNECT_TIMEOUT": int(env("OLLAMA_CONNECT_TIMEOUT", "5")),
        "OLLAMA_BASE_URL": env("OLLAMA_BASE_URL", "http://ollama:11434"),
    }
    globals().update(values)
    from django.conf import settings as django_settings

    for key, value in values.items():
        setattr(django_settings, key, value)


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
DEBUG = env("DJANGO_DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]
if "*" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("*")
RETRIEVAL_MIN_SCORE = float(env("RETRIEVAL_MIN_SCORE", "0.35"))
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "corsheaders",
    "chatbot",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "chatbot.middleware.TenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env("DJANGO_DB_PATH", str(BASE_DIR / "db.sqlite3")),
    }
}
DATABASE_ROUTERS = ["chatbot.tenant_router.TenantRouter"]

TENANT_PG_HOST = env("TENANT_PG_HOST", "")
TENANT_PG_PORT = env("TENANT_PG_PORT", "5432")
TENANT_PG_USER = env("TENANT_PG_USER", "postgres")
TENANT_PG_PASSWORD = env("TENANT_PG_PASSWORD", "")
TENANT_PG_MAINTENANCE_DB = env("TENANT_PG_MAINTENANCE_DB", "postgres")
TENANT_DB_DIR = env("TENANT_DB_DIR", str(BASE_DIR / "tenants"))

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = Path(env("STATIC_ROOT", str(BASE_DIR / "staticfiles")))

MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Chatbot API",
    "DESCRIPTION": (
        "Sign in from Authorize is not used. Call GET /api/auth/csrf/, then POST /api/auth/login/. "
        "The browser keeps the session, and later requests on this page send the CSRF token. "
        "The chatbot answers from uploaded files and a database you connect."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
        "tryItOutEnabled": True,
    },
}

CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in env("CORS_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",")
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in env("CSRF_TRUSTED_ORIGINS", ",".join(CORS_ALLOWED_ORIGINS)).split(",")
    if o.strip()
]

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE", "False").lower() == "true"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE", "False").lower() == "true"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

OLLAMA_BASE_URL = env("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_CHAT_MODEL = env("OLLAMA_CHAT_MODEL", "qwen2.5:3b")
OLLAMA_EMBEDDING_MODEL = env("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
OLLAMA_VISION_MODEL = env("OLLAMA_VISION_MODEL", "")
OLLAMA_TIMEOUT = int(env("OLLAMA_TIMEOUT", "300"))
OLLAMA_CONNECT_TIMEOUT = int(env("OLLAMA_CONNECT_TIMEOUT", "5"))

# ollama | azure | openai (chatgpt). MODEL_NAME is accepted as the Azure deployment.
LLM_PROVIDER = env("LLM_PROVIDER", "ollama").strip().lower()
EMBEDDING_PROVIDER = env("EMBEDDING_PROVIDER", "ollama").strip().lower()

AZURE_ENDPOINT = env("AZURE_ENDPOINT", "").rstrip("/")
AZURE_API_KEY = env("AZURE_API_KEY", "") or env("API_KEY", "")
AZURE_API_VERSION = env("AZURE_API_VERSION", "") or env("API_VERSION", "2025-04-01-preview")
AZURE_CHAT_DEPLOYMENT = (
    env("AZURE_CHAT_DEPLOYMENT", "")
    or env("AZURE_DEPLOYMENT", "")
    or env("MODEL_NAME", "")
)
AZURE_EMBEDDING_DEPLOYMENT = env("AZURE_EMBEDDING_DEPLOYMENT", "") or env(
    "EMBEDDING_MODEL_NAME", ""
)

OPENAI_API_KEY = env("OPENAI_API_KEY", "")
OPENAI_BASE_URL = env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_CHAT_MODEL = env("OPENAI_CHAT_MODEL", "") or env("MODEL_NAME", "gpt-4o-mini")
OPENAI_EMBEDDING_MODEL = env("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

DATABASE_CONTEXT_LIMIT = int(env("DATABASE_CONTEXT_LIMIT", "20"))

MAX_UPLOAD_SIZE_MB = int(env("MAX_UPLOAD_SIZE_MB", "25"))
ALLOWED_UPLOAD_EXTENSIONS = [
    e.strip().lower()
    for e in env(
        "ALLOWED_UPLOAD_EXTENSIONS",
        ".pdf,.docx,.xlsx,.csv,.txt,.md,.json,.png,.jpg,.jpeg,.webp",
    ).split(",")
]

CHUNK_SIZE = int(env("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(env("CHUNK_OVERLAP", "100"))
RETRIEVAL_TOP_K = int(env("RETRIEVAL_TOP_K", "5"))
RETRIEVAL_MIN_SCORE = float(env("RETRIEVAL_MIN_SCORE", "0.35"))
STRICT_DOCUMENTS_DEFAULT = bool(env("STRICT_DOCUMENTS_DEFAULT", "True"))
APPROVED_FOLDER_ROOTS = [
    p.strip()
    for p in env("APPROVED_FOLDER_ROOTS", str(BASE_DIR / "approved_folders")).split(";")
    if p.strip()
]

# One Qdrant collection per user. The crawl embeds pages locally, then stores them there.
QDRANT_URL = env("QDRANT_URL", "http://127.0.0.1:6333")
WEB_EMBED_MODEL = env("WEB_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
FASTEMBED_CACHE_PATH = env("FASTEMBED_CACHE_PATH", str(BASE_DIR / "fastembed-cache"))