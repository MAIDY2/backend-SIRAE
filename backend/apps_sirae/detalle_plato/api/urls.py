from django.urls import include, path
from .router import router_detalle_plato

urlpatterns = [
    path('', include(router_detalle_plato.urls)),
]