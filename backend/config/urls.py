from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


# Configuración de Swagger para documentar la API SIRAE
schema_view = get_schema_view(
    openapi.Info(
        title="SIRAE API",
        default_version="v1",
        description="Documentación de endpoints del sistema SIRAE",
    ),
    url=getattr(settings, "BACKEND_URL", "https://backend-sirae-pyim.onrender.com"),
    public=True,
    permission_classes=(permissions.AllowAny,),
    authentication_classes=(),
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # Endpoint central de la API
    path("api/", include("apps_sirae.api.urls")),

    # Documentación Swagger
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path(
        "api/swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui-api",
    ),

    # Documentación Redoc
    path(
        "redoc/",
        schema_view.with_ui("redoc", cache_timeout=0),
        name="schema-redoc",
    ),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
