from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apps_sirae.api.urls')),

    path('api/jornadas/', include('apps_sirae.jornadas.api.urls')),
    path('api/categorias-inventario/', include('apps_sirae.categorias_inventario.api.urls')),
    path('api/menus/', include('apps_sirae.menus.api.urls')),
]
