from django.urls import include, path
from .api.router import router_movimientos_inventario

urlpatterns = [
    path('', include(router_movimientos_inventario.urls)),
]