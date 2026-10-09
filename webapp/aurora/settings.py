"""Django settings for aurora.

O banco padrão do projeto é o PostgreSQL definido no .env (variáveis ``PG*``,
o mesmo banco usado pela CLI via ``src/db.py``). Tudo — usuários, consultas
salvas, histórico de forecast/QA, conversas dos chats e os dados SINAM
(``sinam_notificacao``) — vive nesse único banco.

O SQLite legado (``db.sqlite3``) só é exposto como a conexão ``legacy_sqlite``
quando o arquivo ainda existe, para permitir migrar/recopiar os dados antigos
com ``manage.py migrate_sqlite_to_pg``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-me-in-prod",
)

DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Origens confiáveis para CSRF (POST via HTTPS de fora — ex.: túnel ngrok/
# Cloudflare para testes). Ex.: DJANGO_CSRF_TRUSTED_ORIGINS="https://*.ngrok-free.app"
CSRF_TRUSTED_ORIGINS = [o.strip() for o in
                        os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# O padrão do Django (desde 3.0) é "same-origin", que omite o header Referer
# em requisições cross-origin. O OpenStreetMap exige Referer nos tiles;
# esta política envia a origem em HTTPS→HTTPS sem vazar o path.
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Recursos PostgreSQL (necessário p/ índices do pgvector — HnswIndex)
    "django.contrib.postgres",
    # Compartilhado (base + auth + home + registry)
    "core",
    # Dados SINAM/VIOLBR (camada semântica — filtros geo/violência p/ dados ao vivo)
    "sinam",
    # Início e painel Aurora (telas vindas do Aurora-Dashborad)
    "painel",
    "mapas",
    # === Aurora Responde — chat único (só Jurema + RAG + dados ao vivo) ===
    "chats.series_temporais.orquestrador",
    # === Guardrails (entrada/saída + limites) ===
    "guardrails",
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

# Permite exibir as telas em <iframe> na MESMA origem (janelas de chat da home).
# Continua bloqueando enquadramento por origens externas (proteção clickjacking).
X_FRAME_OPTIONS = "SAMEORIGIN"

ROOT_URLCONF = "aurora.urls"

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

WSGI_APPLICATION = "aurora.wsgi.application"

# Banco padrão: PostgreSQL do .env (mesmas variáveis PG* da CLi/src/db.py).
# Usa o driver psycopg (v3), já presente no projeto.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("PGDATABASE", "Aurola"),
        "USER": os.getenv("PGUSER", "postgres"),
        "PASSWORD": os.getenv("PGPASSWORD", ""),
        "HOST": os.getenv("PGHOST", "localhost"),
        "PORT": os.getenv("PGPORT", "5432"),
        # A base foi reorganizada: tabelas ORM no schema `django`, dados brutos
        # (VIOLBR etc.) no schema `sinan`. O search_path faz nomes não
        # qualificados resolverem nos dois; `public` mantém compatibilidade.
        "OPTIONS": {
            "options": f"-c search_path={os.getenv('DJANGO_DB_SCHEMA', 'django')},sinan,public",
        },
    }
}

# Conexão legada só-leitura para o SQLite antigo. Exposta apenas enquanto o
# arquivo existir, para o comando `migrate_sqlite_to_pg` copiar os dados.
# Quando o backup não for mais necessário, basta apagar/renomear o db.sqlite3.
_LEGACY_SQLITE = BASE_DIR / "db.sqlite3"
if _LEGACY_SQLITE.exists():
    DATABASES["legacy_sqlite"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _LEGACY_SQLITE,
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# ---------------------------------------------------------------------------
# Cache / Valkey (guardrails — contadores de rate limit)
# Com VALKEY_URL usa django-redis; sem URL, LocMemCache (dev sem Valkey).
# ---------------------------------------------------------------------------
_VALKEY_URL = os.getenv("VALKEY_URL", "").strip()
if _VALKEY_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": _VALKEY_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            "KEY_PREFIX": "aurora",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "aurora-dev",
        }
    }

# Limites alinhados à frente de segurança (encaminhamentos 25 / 27).
AURORA_MAX_INPUT_CHARS = int(os.getenv("AURORA_MAX_INPUT_CHARS", "2000"))
GUARDRAILS_RATE_LIMIT_PER_MIN = int(os.getenv("GUARDRAILS_RATE_LIMIT_PER_MIN", "10"))
GUARDRAILS_RATE_LIMIT_PER_DAY = int(os.getenv("GUARDRAILS_RATE_LIMIT_PER_DAY", "200"))
# Encaminhamento 26 — detecção de entrada/saída.
GUARDRAILS_INJECTION_THRESHOLD = float(os.getenv("GUARDRAILS_INJECTION_THRESHOLD", "0.70"))
GUARDRAILS_SUPPRESS_BELOW = int(os.getenv("GUARDRAILS_SUPPRESS_BELOW", "5"))
