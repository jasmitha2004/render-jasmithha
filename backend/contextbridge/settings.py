"""
Django settings for ContextBridge AI.

Environment-driven: local development works with zero configuration (SQLite,
DEBUG on); production (Render) is configured entirely through env vars.
"""
import logging
import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / '.env')


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ('true', '1', 'yes', 'on')


def env_list(name: str, default=None):
    raw = os.getenv(name, '')
    items = [i.strip() for i in raw.split(',') if i.strip()]
    return items or (default or [])


# --- Core -------------------------------------------------------------------
DEBUG = env_bool('DJANGO_DEBUG', True)  # local default; render.yaml sets False

_DEV_SECRET = 'django-insecure-dev-key-change-in-production'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', _DEV_SECRET)
if not DEBUG and SECRET_KEY in (_DEV_SECRET, 'replace-with-secure-key', ''):
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must be set to a strong value when DJANGO_DEBUG is False.')

# --- Hosts / CSRF -----------------------------------------------------------
# Render injects RENDER_EXTERNAL_HOSTNAME for each web service.
RENDER_HOST = os.getenv('RENDER_EXTERNAL_HOSTNAME', '')
if DEBUG:
    ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', ['localhost', '127.0.0.1', '[::1]', 'testserver'])
else:
    ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS')
if RENDER_HOST and RENDER_HOST not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_HOST)

CSRF_TRUSTED_ORIGINS = env_list(
    'CSRF_TRUSTED_ORIGINS',
    ['http://localhost:8501', 'http://127.0.0.1:8501'] if DEBUG else [],
)
if RENDER_HOST:
    origin = f'https://{RENDER_HOST}'
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

# --- Apps -------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'rest_framework',
    'contextbridge_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'contextbridge.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'contextbridge.wsgi.application'

# --- Database ---------------------------------------------------------------
# DATABASE_URL (PostgreSQL on Render) wins; otherwise SQLite for local dev.
_sqlite_path = os.environ.get('SQLITE_PATH', str(BASE_DIR / 'db.sqlite3'))
DATABASES = {
    'default': dj_database_url.config(
        env='DATABASE_URL',
        default=f'sqlite:///{_sqlite_path}',
        conn_max_age=600,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# --- Static & media ---------------------------------------------------------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'
        if DEBUG else 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}
MEDIA_URL = '/media/'
# On Render, point MEDIA_ROOT at a persistent disk mount (e.g. /var/data/media).
# Without a disk the filesystem is ephemeral: uploads vanish on redeploy.
MEDIA_ROOT = Path(os.getenv('MEDIA_ROOT', str(BASE_DIR / 'media')))
MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', '10'))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_MB * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = DATA_UPLOAD_MAX_MEMORY_SIZE

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# --- Session / security -----------------------------------------------------
# The API is consumed server-to-server by Streamlit (the browser never talks to
# it directly), so session cookies live inside the Streamlit process.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # Render terminates TLS
    SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', True)
    SECURE_REDIRECT_EXEMPT = [r'^health/$', r'^api/health/$']  # platform health probes
    # Secure cookies need HTTPS. Set SECURE_COOKIES=False only to simulate production over plain http locally.
    SESSION_COOKIE_SECURE = env_bool('SECURE_COOKIES', True)
    CSRF_COOKIE_SECURE = env_bool('SECURE_COOKIES', True)
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '3600'))
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

# --- AI ---------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
ANTHROPIC_MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-5')
ANTHROPIC_TIMEOUT = float(os.getenv('ANTHROPIC_TIMEOUT', '30'))

# --- Logging ----------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {'format': '%(asctime)s %(levelname)s %(name)s: %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'standard'},
    },
    'root': {'handlers': ['console'], 'level': os.getenv('LOG_LEVEL', 'INFO')},
    'loggers': {
        'contextbridge': {'handlers': ['console'], 'level': os.getenv('LOG_LEVEL', 'INFO'), 'propagate': False},
        'django.request': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}
