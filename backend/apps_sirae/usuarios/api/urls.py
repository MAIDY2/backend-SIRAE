from django.urls import path, include
from rest_framework_simplejwt.views import TokenVerifyView

from apps_sirae.usuarios.api.router import router_usuarios
from apps_sirae.usuarios.api.views import (
    CustomTokenRefreshView,
    LoginView,
    LogoutView,
    RegistroView,
    ValidarSesionActivaView,
    MigrarDBView,
    DesbloquearUsuarioView,
)


urlpatterns = [
    path('', include(router_usuarios.urls)),

    path(
        'auth/migrar/',
        MigrarDBView.as_view(),
        name='migrar_db'
    ),
    path(
        'auth/desbloquear/',
        DesbloquearUsuarioView.as_view(),
        name='desbloquear_usuario'
    ),
    path(
        'auth/login/',
        LoginView.as_view(),
        name='login'
    ),
    path(
        'auth/logout/',
        LogoutView.as_view(),
        name='logout'
    ),
    path(
        'auth/token/refresh/',
        CustomTokenRefreshView.as_view(),
        name='token_refresh'
    ),
    path(
        'auth/token/verify/',
        TokenVerifyView.as_view(),
        name='token_verify'
    ),
    path(
        'auth/verify/',
        ValidarSesionActivaView.as_view(),
        name='auth_verify'
    ),
    path(
        'auth/validar-sesion/',
        ValidarSesionActivaView.as_view(),
        name='auth_validar_sesion'
    ),
]
