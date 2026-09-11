from django.urls import include, path
from .router import router_unidades_medida

urlpatterns = [
    path('', include(router_unidades_medida.urls)),
]