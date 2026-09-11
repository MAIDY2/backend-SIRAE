from django.urls import include, path
from .router import router_inventario

urlpatterns = [
    path('', include(router_inventario.urls)),
]