from django.urls import include, path

from .api.router import router_pasos_preparacion

urlpatterns = [
    path('', include(router_pasos_preparacion.urls)),
]
