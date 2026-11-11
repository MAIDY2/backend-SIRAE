from django.urls import include, path
from apps_sirae.mensajes.api.router import router_mensajes

urlpatterns = [
    path('', include(router_mensajes.urls)),
]
