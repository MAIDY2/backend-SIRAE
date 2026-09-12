from django.urls import include, path, re_path

from .api.router import pasos_preparacion_router

urlpatterns = [
    path('', include(router_contratos.urls)),
     ]