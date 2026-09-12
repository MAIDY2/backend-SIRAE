from django.urls import include, path, re_path

from .api.router import router_contratos

urlpatterns = [
    path('', include(router_contratos.urls)),
     ]