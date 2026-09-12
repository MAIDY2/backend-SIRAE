from django.urls import include, path

from .router import router_categorias


urlpatterns = [
    path('', include(router_categorias.urls)),
]
