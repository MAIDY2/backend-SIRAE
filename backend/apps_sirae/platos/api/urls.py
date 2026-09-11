from django.urls import include, path
from .router import router_platos

urlpatterns = [
    path('', include(router_platos.urls)),
]