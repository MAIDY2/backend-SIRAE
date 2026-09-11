from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/contratos-pae/', include('apps_sirae.contratos_pae.urls')),
    path('api/contratos/', include('apps_sirae.contratos_pae.urls')),
    path('api/preparacion-asignada/', include('apps_sirae.preparacion_asignada.urls')),
    path('api/preparacion_asignada/', include('apps_sirae.preparacion_asignada.urls')),
    path('api/preparaciones-asignadas/', include('apps_sirae.preparacion_asignada.urls')),
    path('api/preparaciones_asignadas/', include('apps_sirae.preparacion_asignada.urls')),
    path('api/preparacion/', include('apps_sirae.preparacion_asignada.urls')),
    path('api/pasos-preparacion/', include('apps_sirae.pasospreparacion.urls')),
    path('api/asistencia-diaria/', include('apps_sirae.asistencia_diaria.urls')),
    path('api/asistencia_diaria/', include('apps_sirae.asistencia_diaria.urls')),
    path('api/', include('apps_sirae.api.urls')),
]