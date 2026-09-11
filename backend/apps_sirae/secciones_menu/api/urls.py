from django.urls import include, path
from .router import router_secciones_menu

urlpatterns = [
    path('', include(router_secciones_menu.urls)),
]