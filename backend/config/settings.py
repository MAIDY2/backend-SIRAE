"""
Django settings for config project.
"""

from datetime import timedelta
import os
import sys
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-pmt1w^!r9=)mza56h*qmjv(31z#l*2ldc71@(ti+5=tc59)l89"
)

DEBUG = os.getenv("DEBUG", "True") == "True"

ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1,testserver,*"
).split(",")

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

CORS_ALLOWED_ORIGINS = [
    "http://localhost:4200",
]

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
STATIC_URL = "static/"

# Correo
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

email_user = os.getenv("EMAIL_HOST_USER", "")

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    f"SIRAE PAE <{email_user}>" if email_user else "SIRAE PAE <no-reply@sirae-pae.edu.co>",
)

EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

sys.path.insert(0, str(BASE_DIR / "apps_sirae"))
CORS_ALLOW_ALL_ORIGINS = True