from django.urls import include, path

from apps_sirae.unidades_medida.api.router import router_unidades_medida
from apps_sirae.secciones_menu.api.router import router_secciones_menu
from apps_sirae.platos.api.router import router_platos
from apps_sirae.platos.views import SubirImagenPlatoView  # <--- Importación de la vista de Cloudinary
from apps_sirae.detalle_plato.api.router import router_detalle_plato
from apps_sirae.preparacion_asignada.api.router import router as router_preparacion_asignada
from apps_sirae.preparacion_asignada.api.views import PreparacionAsignadaApiViewSet

from apps_sirae.asistencia_diaria.api.router import router_asistencia_diaria
from apps_sirae.menus.api.router import router_menus
from apps_sirae.entregas.api.router import router_entregas
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
from apps_sirae.categorias_inventario.api.router import router_categorias
from apps_sirae.tipos_mercado.api.router import router_tipos_mercado
from apps_sirae.instituciones.api.router import router as router_instituciones
from apps_sirae.sedes.api.router import router as router_sedes
from apps_sirae.sede_jornada.api.router import router as router_sede_jornadas

from apps_sirae.usuarios.api.password_reset import (
    CambiarPasswordView,
    ConfirmarRecuperacionPasswordView,
    SolicitarRecuperacionPasswordView,
    ValidarTokenPasswordView,
)
from apps_sirae.usuarios.api.views import ConfirmarCodigoRecuperacionPasswordView, RecuperarPasswordView


urlpatterns = [
    path('', include('apps_sirae.roles.api.urls')),
    path('', include('apps_sirae.usuarios.api.urls')),
    
    # Rutas directas y corregidas (sin duplicar 'api/')
    path('auth/recuperar-password/', RecuperarPasswordView.as_view(), name='recuperar-password'),
    path(
        'auth/confirmar-recuperacion-password/',
        ConfirmarCodigoRecuperacionPasswordView.as_view(),
        name='confirmar-recuperacion-password',
    ),
    path('auth/password-reset/validar-token/', ValidarTokenPasswordView.as_view(), name='password-reset-validar-token'),
    path('auth/password-reset/confirmar/', ConfirmarRecuperacionPasswordView.as_view(), name='password-reset-confirmar'),
    path('auth/cambiar-password/', CambiarPasswordView.as_view(), name='cambiar-password'),

    path('', include(router_unidades_medida.urls)),
    path('', include(router_secciones_menu.urls)),
    
    # --- RUTA PARA SUBIR LA IMAGEN DEL PLATO ---
    path('platos/<int:pk>/subir-imagen/', SubirImagenPlatoView.as_view(), name='subir-imagen-plato'),
    path('', include(router_platos.urls)),
    # -------------------------------------------

    path('', include(router_detalle_plato.urls)),
    path('preparacion-asignada', PreparacionAsignadaApiViewSet.as_view({'get': 'list', 'post': 'create'}), name='preparacion-asignada-list'),
    path('preparacion-asignada/<int:pk>', PreparacionAsignadaApiViewSet.as_view({'get': 'retrieve', 'delete': 'destroy'}), name='preparacion-asignada-detail'),
    path('', include(router_preparacion_asignada.urls)),

    path('', include(router_asistencia_diaria.urls)),
    path('', include(router_menus.urls)),
    path('', include(router_entregas.urls)),
    path('', include(router_entradas_inventario.urls)),
    path('', include(router_salidas_inventario.urls)),
    
    path('', include(router_notificaciones.urls)),

    # --- RUTA DE INGREDIENTES ---
    path('', include(router_ingredientes.urls)),
    # ----------------------------

    path('', include(router_turnos.urls)),
    path('', include(router_usuario_turno.urls)),

    path('', include(router_grados.urls)),
    path('', include(router_gramage.urls)),
    path('', include(router_inventario.urls)),
    path('', include(router_contratos.urls)),
    path('', include(router_contrato_seccion_menu.urls)),
    path('', include(router_jornadas.urls)),
    path('', include(router_categorias.urls)),
    path('', include(router_tipos_mercado.urls)),
    path('', include(router_instituciones.urls)),
    path('', include(router_sedes.urls)),
    path('', include(router_sede_jornadas.urls))
]