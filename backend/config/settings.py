import os
import sys
from pathlib import Path
from datetime import timedelta

try:
    import cloudinary
    import cloudinary_storage
except ImportError:
    cloudinary = None
    cloudinary_storage = None
import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

DEBUG = os.getenv("DEBUG", "False").strip().lower() in {
    "1", "true", "yes", "on"
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = (
            "django-insecure-local-development-only-change-this-key"
        )
    else:
        raise ImproperlyConfigured(
            "Debes configurar SECRET_KEY en las variables de entorno."
        )


def parse_env_list(value, default=""):
    value = value if value is not None else default
    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def parse_env_int(value, default=0):
    if value is None:
        return default
    try:
        val_str = str(value).strip()
        return int(val_str) if val_str else default
    except (ValueError, TypeError):
        return default


ALLOWED_HOSTS = parse_env_list(
    os.getenv("ALLOWED_HOSTS"),
    "localhost,127.0.0.1,0.0.0.0,testserver,.onrender.com,backend-sirae-pyim.onrender.com,backend-sirae-t9zi.onrender.com",
)
for host in [
    "backend-sirae-pyim.onrender.com",
    "backend-sirae-t9zi.onrender.com",
    ".onrender.com",
    "0.0.0.0",
    "localhost",
    "127.0.0.1",
]:
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

APPEND_SLASH = False

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Cloudinary Apps (cuando están instaladas)
    *(["cloudinary_storage", "cloudinary"] if (cloudinary and cloudinary_storage) else []),
    # Rest Framework & Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_yasg",
    "corsheaders",
    # Aplicaciones SIRAE
    "apps_sirae.roles",
    "apps_sirae.usuarios",
    "apps_sirae.instituciones",
    "apps_sirae.sedes",
    "apps_sirae.asistencia_diaria",
    "apps_sirae.jornadas",
    "apps_sirae.sede_jornada",
    "apps_sirae.turnos",
    "apps_sirae.usuario_turno",
    "apps_sirae.grados",
    "apps_sirae.contratos_pae",
    "apps_sirae.contratos_seccion_menu",
    "apps_sirae.entregas",
    "apps_sirae.notificaciones",
    "apps_sirae.mensajes",
    "apps_sirae.inventario",
    "apps_sirae.entradas_inventario",
    "apps_sirae.salidas_inventario",
    "apps_sirae.facturas_compra",
    "apps_sirae.tipos_mercado",
    "apps_sirae.categorias_inventario",
    "apps_sirae.unidades_medida",
    "apps_sirae.receta_componente",
    "apps_sirae.ia_sugerencias",
    "apps_sirae.menus",
    "apps_sirae.secciones_menu",
    "apps_sirae.ingredientes",
    "apps_sirae.platos",
    "apps_sirae.detalle_plato",
    "apps_sirae.pasospreparacion",
    "apps_sirae.preparacion_asignada",
    "apps_sirae.gramage",
    "apps_sirae.reportes",
    "apps_sirae.reconocimiento_facial.apps.ReconocimientoFacialConfig",

]

AUTH_USER_MODEL = "usuarios.Usuario"

LOGIN_MAX_FAILED_ATTEMPTS = parse_env_int(os.getenv("LOGIN_MAX_FAILED_ATTEMPTS"), 5)
LOGIN_LOCKOUT_DURATION_MINUTES = parse_env_int(
    os.getenv("LOGIN_LOCKOUT_DURATION_MINUTES"), 15
)

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "USER_ID_FIELD": "id_usuario",
    "USER_ID_CLAIM": "user_id",
    "AUTH_HEADER_TYPES": ("Bearer",),
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
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

if 'test' in sys.argv:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
    DATABASE_URL = ''
else:
    DATABASE_URL = os.getenv('DATABASE_URL', '').strip()

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }
elif DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    raise ImproperlyConfigured(
        "Debes configurar DATABASE_URL en producción."
    )

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Configuración de Cloudinary para almacenamiento multimedia persistente
MEDIA_URL = "/media/"
if cloudinary and cloudinary_storage:
    DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

# ==============================================================================
# Configuración de Correo Electrónico (Google SMTP / Gmail y Brevo opcional)
# ==============================================================================
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
).strip()
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com").strip()
EMAIL_PORT = parse_env_int(os.getenv("EMAIL_PORT"), 587)
EMAIL_USE_SSL = (
    os.getenv("EMAIL_USE_SSL", "False").strip().lower() in {"1", "true", "yes", "on"}
)
EMAIL_USE_TLS = (
    False
    if EMAIL_USE_SSL
    else (
        os.getenv("EMAIL_USE_TLS", "True").strip().lower()
        in {"1", "true", "yes", "on"}
    )
)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
# Las contraseñas de aplicación de Gmail suelen copiarse con espacios (4 grupos de 4)
EMAIL_HOST_PASSWORD = (
    os.getenv("EMAIL_HOST_PASSWORD", "").replace(" ", "").strip()
)
EMAIL_TIMEOUT = parse_env_int(os.getenv("EMAIL_TIMEOUT"), 15)

# Soporte opcional para API HTTP directa de Brevo (solo si se configura por entorno)
BREVO_API_KEY = (
    os.getenv("BREVO_API_KEY", "").strip()
    or os.getenv("SENDINBLUE_API_KEY", "").strip()
)
if BREVO_API_KEY and EMAIL_BACKEND == "anymail.backends.brevo.EmailBackend":
    if "anymail" not in INSTALLED_APPS:
        INSTALLED_APPS += ["anymail"]
    ANYMAIL = {
        "BREVO_API_KEY": BREVO_API_KEY,
    }

DEFAULT_FROM_EMAIL = (
    os.getenv("DEFAULT_FROM_EMAIL", "").strip()
    or EMAIL_HOST_USER
    or "noreply@sirae.local"
)
BREVO_SENDER_EMAIL = (
    os.getenv("BREVO_SENDER_EMAIL", "").strip()
    or DEFAULT_FROM_EMAIL
)

BACKEND_URL = (
    os.getenv("BACKEND_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or "https://backend-sirae-pyim.onrender.com"
).strip().rstrip("/")

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "https://backend-sirae-pyim.onrender.com" if not DEBUG else "http://localhost:4200",
).strip().rstrip("/")

PASSWORD_RESET_EXPOSE_CODE = (
    os.getenv("PASSWORD_RESET_EXPOSE_CODE", "False")
    .strip()
    .lower() in {"1", "true", "yes", "on"}
)

PASSWORD_RESET_EXPOSE_CODE_EMAILS = {
    email.casefold()
    for email in parse_env_list(
        os.getenv("PASSWORD_RESET_EXPOSE_CODE_EMAILS"),
        "",
    )
}

sys.path.insert(0, str(BASE_DIR / "apps_sirae"))

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps_sirae.usuarios.authentication.CustomJWTAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
}

CORS_ALLOW_ALL_ORIGINS = os.getenv(
    "CORS_ALLOW_ALL_ORIGINS",
    "True" if DEBUG else "False",
).strip().lower() in {"1", "true", "yes", "on"}

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = parse_env_list(
    os.getenv("CORS_ALLOWED_ORIGINS"),
    (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:4200,"
        "http://127.0.0.1:4200,"
        "https://backend-sirae-pyim.onrender.com"
    ),
)
for origin in [
    "https://backend-sirae-pyim.onrender.com",
    "https://backend-sirae-t9zi.onrender.com",
]:
    if origin not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(origin)

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^http://127\.0\.0\.1:\d+$",
    r"^https://.*\.vercel\.app$",
    r"^https://.*\.onrender\.com$",
]

CSRF_TRUSTED_ORIGINS = parse_env_list(
    os.getenv("CSRF_TRUSTED_ORIGINS"),
    (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:4200,"
        "http://127.0.0.1:4200,"
        "https://*.onrender.com,"
        "https://backend-sirae-pyim.onrender.com,"
        "https://backend-sirae-t9zi.onrender.com"
    ),
)
for origin in [
    "https://*.onrender.com",
    "https://backend-sirae-pyim.onrender.com",
    "https://backend-sirae-t9zi.onrender.com",
]:
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Escribe Bearer seguido de tu token JWT",
        }
    },
    "SECURITY_REQUIREMENTS": [
        {"Bearer": []},
    ],
    "USE_SESSION_AUTH": False,
}

if cloudinary:
    _cld_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip().strip('"').strip("'")
    _cld_key = os.getenv("CLOUDINARY_API_KEY", "").strip().strip('"').strip("'")
    _cld_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip().strip('"').strip("'")
    _cld_url = os.getenv("CLOUDINARY_URL", "").strip().strip('"').strip("'")

    _cld_placeholders = {"", "tu_cloud_name", "tu_api_key", "tu_api_secret"}
    if (
        _cld_name not in _cld_placeholders
        and _cld_key not in _cld_placeholders
        and _cld_secret not in _cld_placeholders
    ):
        cloudinary.config(
            cloud_name=_cld_name,
            api_key=_cld_key,
            api_secret=_cld_secret,
            secure=True,
        )
        CLOUDINARY_STORAGE = {
            "CLOUD_NAME": _cld_name,
            "API_KEY": _cld_key,
            "API_SECRET": _cld_secret,
        }
    elif _cld_url:
        cloudinary.config(cloudinary_url=_cld_url, secure=True)
    else:
        cloudinary.config(secure=True)

DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

SECURE_SSL_REDIRECT = os.getenv(
    "SECURE_SSL_REDIRECT", "False"
).strip().lower() in {"1", "true", "yes", "on"}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    if SECURE_SSL_REDIRECT:
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# ==============================================================================
# CONFIGURACIÓN DE MONGODB ATLAS (Módulo de Inteligencia Artificial)
# ==============================================================================
if "test" in sys.argv:
    MONGO_URI = ""
    MONGO_DISABLE_ENV_FALLBACK = True
else:
    MONGO_DISABLE_ENV_FALLBACK = False
    MONGO_URI = (
        os.getenv("MONGO_URI")
        or os.getenv("MONGODB_URI")
        or os.getenv("MONGO_URL")
        or os.getenv("MONGODB_URL")
        or os.getenv("MONGO_ATLAS_URI")
        or os.getenv("MONGODB_ATLAS_URI")
        or os.getenv("MONGO_CONNECTION_STRING")
        or ""
    ).replace("\r", "").replace("\n", "").strip()
MONGO_DB_NAME = (
    os.getenv("MONGO_DB_NAME")
    or os.getenv("MONGODB_DB_NAME")
    or os.getenv("MONGO_DATABASE")
    or os.getenv("MONGODB_DATABASE")
    or "sirae_ia"
).strip()
