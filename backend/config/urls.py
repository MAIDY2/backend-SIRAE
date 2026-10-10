from django.contrib import admin
from django.urls import include, path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

# Configuración de drf-yasg con autenticación Bearer por esquema
schema_view = get_schema_view(
    openapi.Info(
        title="SIRAE API",
        default_version='v1',
        description="Documentación de endpoints del sistema SIRAE",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Endpoint central que orquesta todos los routers de las apps
    path('api/', include('apps_sirae.api.urls')),

    # Documentación Swagger y Redoc
    path(
        'swagger/',
        schema_view.with_ui('swagger', cache_timeout=0),
        name='schema-swagger-ui'
    ),
    path(
        'redoc/',
        schema_view.with_ui('redoc', cache_timeout=0),
        name='schema-redoc'
    ),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()