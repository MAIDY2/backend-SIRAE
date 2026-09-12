from django.urls import path, include

from apps_sirae.roles.api.router import router_roles


urlpatterns = [
    path('', include(router_roles.urls)),
]