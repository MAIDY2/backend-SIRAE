from django.urls import include, path


from apps_sirae.unidades_medida.api.router import router_unidades_medida
from apps_sirae.secciones_menu.api.router import router_secciones_menu
from apps_sirae.platos.api.router import router_platos
from apps_sirae.detalle_plato.api.router import router_detalle_plato


from apps_sirae.asistencia_diaria.api.router import router_asistencia_diaria
from apps_sirae.entregas.api.router import router_entregas
from apps_sirae.movimientos_inventario.api.router import router_movimientos_inventario
from apps_sirae.notificaciones.api.router import router_notificaciones


from apps_sirae.ingredientes.api.router import router_ingredientes
from apps_sirae.turnos.api.router import router_turnos
from apps_sirae.usuario_turno.api.router import router_usuario_turno


urlpatterns = [
    path('', include('apps_sirae.usuarios.api.urls')),


    path('', include(router_unidades_medida.urls)),
    path('', include(router_secciones_menu.urls)),
    path('', include(router_platos.urls)),
    path('', include(router_detalle_plato.urls)),


    path('', include(router_asistencia_diaria.urls)),
    path('', include(router_entregas.urls)),
    path('', include(router_movimientos_inventario.urls)),
    path('', include(router_notificaciones.urls)),


    path('', include(router_ingredientes.urls)),
    path('', include(router_turnos.urls)),
    path('', include(router_usuario_turno.urls)),
]
