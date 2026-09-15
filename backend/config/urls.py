from django.contrib import admin
from django.urls import include, path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Configuración del esquema de Swagger
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
    
    # Endpoints de la API
    path('api/', include('apps_sirae.api.urls')),

    # Rutas individuales (opcional si ya están dentro de apps_sirae.api.urls)
    path('api/jornadas/', include('apps_sirae.jornadas.api.urls')),
    path('api/categorias-inventario/', include('apps_sirae.categorias_inventario.api.urls')),
    path('api/menus/', include('apps_sirae.menus.api.urls')),

    # Documentación Swagger y Redoc
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]