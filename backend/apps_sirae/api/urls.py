from django.urls import include, path


urlpatterns = [
    path('asistencia-diaria/', include('apps_sirae.asistencia_diaria.urls')),
    path('entregas/', include('apps_sirae.entregas.urls')),
    path('notificaciones/', include('apps_sirae.notificaciones.urls')),
]