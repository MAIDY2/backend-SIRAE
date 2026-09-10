from django.urls import include, path
from apps_sirae.inventario.api.router import router_inventario
from apps_sirae.unidades_medida.api.router import router_unidades_medida
from apps_sirae.secciones_menu.api.router import router_secciones_menu
from apps_sirae.platos.api.router import router_platos
from apps_sirae.detalle_plato.api.router import router_detalle_plato


urlpatterns = [
    path('', include('apps_sirae.usuarios.api.urls')),
    path('', include(router_inventario.urls)),
    path('', include(router_unidades_medida.urls)),
    path('', include(router_secciones_menu.urls)),
    path('', include(router_platos.urls)),
    path('', include(router_detalle_plato.urls)),
    path('asistencia-diaria/', include('apps_sirae.asistencia_diaria.urls')),
    path('entregas/', include('apps_sirae.entregas.urls')),
    path('movimientos-inventario/', include('apps_sirae.movimientos_inventario.urls')),
    path('notificaciones/', include('apps_sirae.notificaciones.urls')),
]