from django.urls import include, path


urlpatterns = [
    path('', include('apps_sirae.usuarios.api.urls')),
    path('asistencia-diaria/', include('apps_sirae.asistencia_diaria.urls')),
    path('entregas/', include('apps_sirae.entregas.urls')),
    path('movimientos-inventario/', include('apps_sirae.movimientos_inventario.urls')),
    path('notificaciones/', include('apps_sirae.notificaciones.urls')),
]