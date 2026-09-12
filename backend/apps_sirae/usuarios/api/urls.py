from django.urls import path, include

from apps_sirae.usuarios.api.router import router_usuarios
from apps_sirae.usuarios.api.views import LoginView, RegistroView


urlpatterns = [
    path('', include(router_usuarios.urls)),

    path(
        'auth/login/',
        LoginView.as_view(),
        name='login'
    ),

    path(
        'auth/registro/',
        RegistroView.as_view(),
        name='registro'
    ),
]