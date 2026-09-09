from django.urls import include, path
from .api.router import router_asistencia_diaria

urlpatterns = [
    path('', include(router_asistencia_diaria.urls)),
]