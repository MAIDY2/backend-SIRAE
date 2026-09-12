from django.urls import include, path

from .router import router_menus


urlpatterns = [
    path('', include(router_menus.urls)),
]
