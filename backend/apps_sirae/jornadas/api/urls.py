from django.urls import include, path

from .router import router_jornadas


urlpatterns = [
    path('', include(router_jornadas.urls)),
]
