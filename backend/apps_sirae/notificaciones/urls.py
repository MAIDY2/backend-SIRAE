from django.urls import include, path
from .api.router import router_notificaciones

urlpatterns = [
    path('', include(router_notificaciones.urls)),
]