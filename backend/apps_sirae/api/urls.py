from django.urls import include, path

urlpatterns = [
    path('pasos-preparacion/', include('apps_sirae.pasospreparacion.api.urls')),
    path('preparacion-asignada/', include('apps_sirae.preparacion_asignada.api.urls')),
    path('contratos/', include('apps_sirae.contratos.api.urls')),
    path('asistencia-diaria/', include('apps_sirae.asistencia_diaria.urls')),
    path('entregas/', include('apps_sirae.entregas.urls')),
    path('movimientos-inventario/', include('apps_sirae.movimientos_inventario.urls')),
    path('notificaciones/', include('apps_sirae.notificaciones.urls')),
]