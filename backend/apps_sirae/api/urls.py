from django.urls import include, path

from apps_sirae.unidades_medida.api.router import router_unidades_medida
from apps_sirae.secciones_menu.api.router import router_secciones_menu
from apps_sirae.platos.api.router import router_platos
from apps_sirae.detalle_plato.api.router import router_detalle_plato
from apps_sirae.preparacion_asignada.api.router import router as router_preparacion_asignada
from apps_sirae.preparacion_asignada.api.views import PreparacionAsignadaApiViewSet

from apps_sirae.asistencia_diaria.api.router import router_asistencia_diaria
from apps_sirae.entregas.api.router import router_entregas
from apps_sirae.movimientos_inventario.api.router import router_movimientos_inventario
from apps_sirae.entradas_inventario.api.router import router_entradas_inventario
from apps_sirae.salidas_inventario.api.router import router_salidas_inventario
from apps_sirae.notificaciones.api.router import router_notificaciones
from apps_sirae.grados.api.router import router_grados
from apps_sirae.gramage.api.router import router_gramage
from apps_sirae.inventario.api.router import router_inventario

from apps_sirae.ingredientes.api.router import router_ingredientes
from apps_sirae.turnos.api.router import router_turnos
from apps_sirae.usuario_turno.api.router import router_usuario_turno
from apps_sirae.contratos_pae.api.router import router_contratos
from apps_sirae.contratos_seccion_menu.api.router import router_contrato_seccion_menu
from apps_sirae.jornadas.api.router import router_jornadas

# Importamos las vistas de recuperación de contraseña desde la app de usuarios
from apps_sirae.usuarios.api.password_reset import (
    CambiarPasswordView,
    ConfirmarRecuperacionPasswordView,
    SolicitarRecuperacionPasswordView,
    ValidarTokenPasswordView,
)


urlpatterns = [
    path('', include('apps_sirae.roles.api.urls')),
    path('', include('apps_sirae.usuarios.api.urls')),
    
    # Rutas directas y corregidas (sin duplicar 'api/')
    path('auth/recuperar-password/', SolicitarRecuperacionPasswordView.as_view(), name='recuperar-password'),
    path('auth/password-reset/validar-token/', ValidarTokenPasswordView.as_view(), name='password-reset-validar-token'),
    path('auth/password-reset/confirmar/', ConfirmarRecuperacionPasswordView.as_view(), name='password-reset-confirmar'),
    path('auth/cambiar-password/', CambiarPasswordView.as_view(), name='cambiar-password'),

    path('', include(router_unidades_medida.urls)),
    path('', include(router_secciones_menu.urls)),
    path('', include(router_platos.urls)),
    path('', include(router_detalle_plato.urls)),
    path('preparacion-asignada', PreparacionAsignadaApiViewSet.as_view({'get': 'list', 'post': 'create'}), name='preparacion-asignada-list'),
    path('preparacion-asignada/<int:pk>', PreparacionAsignadaApiViewSet.as_view({'get': 'retrieve', 'delete': 'destroy'}), name='preparacion-asignada-detail'),
    path('', include(router_preparacion_asignada.urls)),

    path('', include(router_asistencia_diaria.urls)),
    path('', include(router_entregas.urls)),
    path('', include(router_movimientos_inventario.urls)),
    path('', include(router_entradas_inventario.urls)),
    path('', include(router_salidas_inventario.urls)),
    
    path('', include(router_notificaciones.urls)),

    path('', include(router_ingredientes.urls)),
    path('', include(router_turnos.urls)),
    path('', include(router_usuario_turno.urls)),

    path('', include(router_grados.urls)),
    path('', include(router_gramage.urls)),
    path('', include(router_inventario.urls)),
    path('', include(router_contratos.urls)),
    path('', include(router_contrato_seccion_menu.urls)),
    path('', include(router_jornadas.urls))
]