from django.urls import include, path

from .router import router_receta_componente


urlpatterns = [
    path('', include(router_receta_componente.urls)),
]
