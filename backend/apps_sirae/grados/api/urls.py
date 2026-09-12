from django.urls import include, path
from .router import router_grados, router_grados_without_slash

urlpatterns = [
    path('', include(router_grados_without_slash.urls)),
    path('', include(router_grados.urls)),
]