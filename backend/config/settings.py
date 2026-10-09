"""
Django settings for config project.
"""

from datetime import timedelta
import os
import sys
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def parse_env_list(value, default):
    raw = value or default
    if isinstance(raw, str):
        return [item.strip() for item in raw.split(",") if item.strip()]
    return [str(item).strip() for item in raw if str(item).strip()]


DEBUG = os.getenv("DEBUG", "True").strip().lower() in {"1", "true", "yes", "on"}

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("SECRET_KEY debe configurarse cuando DEBUG está desactivado.")
    SECRET_KEY = "django-insecure-local-development-only"

ALLOWED_HOSTS = parse_env_list(
    os.getenv("ALLOWED_HOSTS"),
    "localhost,127.0.0.1,0.0.0.0,testserver,.onrender.com"
)

APPEND_SLASH = False

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # Requerido si BLACKLIST_AFTER_ROTATION = True
    "drf_yasg",
    "corsheaders",

    "apps_sirae.roles",
    "apps_sirae.usuarios",
    "apps_sirae.asistencia_diaria",
    "apps_sirae.entregas",
    "apps_sirae.movimientos_inventario",
    "apps_sirae.entradas_inventario",
    "apps_sirae.salidas_inventario",
    "apps_sirae.notificaciones",
    "apps_sirae.inventario",
    "apps_sirae.jornadas",
    "apps_sirae.categorias_inventario",
    "apps_sirae.menus",
    "apps_sirae.turnos",
    "apps_sirae.unidades_medida",
    "apps_sirae.secciones_menu",
    "apps_sirae.ingredientes",
    "apps_sirae.platos",
    "apps_sirae.detalle_plato",
    "apps_sirae.usuario_turno",
    "apps_sirae.contratos_pae",
    "apps_sirae.pasospreparacion",
    "apps_sirae.preparacion_asignada",
    "apps_sirae.gramage",
    "apps_sirae.grados",
    'apps_sirae.contratos_seccion_menu',
]

AUTH_USER_MODEL = "usuarios.Usuario"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").strip()

# Configuración global de Rest Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'apps_sirae.usuarios.authentication.CustomJWTAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

CORS_ALLOWED_ORIGINS = parse_env_list(
    os.getenv("CORS_ALLOWED_ORIGINS"),
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4200,http://127.0.0.1:4200"
)
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = parse_env_list(
    os.getenv("CSRF_TRUSTED_ORIGINS"),
    "http://localhost:5173,http://127.0.0.1:5173,https://*.onrender.com"
)

# Configuración JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),   # Ajusta a timedelta(days=1) si estás en desarrollo
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'USER_ID_FIELD': 'id_usuario',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Configuración Swagger (Permite ingresar token Bearer en la interfaz web)
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
            'description': 'Formato: Bearer <tu_token_jwt>'
        }
    },
    'USE_SESSION_AUTH': False,
}

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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

# Database
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }
elif not DEBUG:
    raise ImproperlyConfigured("DATABASE_URL debe configurarse cuando DEBUG está desactivado.")
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "False").strip().lower() in {"1", "true", "yes", "on"}
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    if SECURE_SSL_REDIRECT:
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# Correo
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").strip().lower() in {"1", "true", "yes", "on"}
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

email_user = os.getenv("EMAIL_HOST_USER", "")

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    f"SIRAE PAE <{email_user}>" if email_user else "SIRAE PAE <no-reply@sirae-pae.edu.co>",
)

EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))

sys.path.insert(0, str(BASE_DIR / "apps_sirae"))
CORS_ALLOW_ALL_ORIGINS = False