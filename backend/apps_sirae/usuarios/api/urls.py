from django.urls import path, include
from rest_framework_simplejwt.views import TokenVerifyView

from apps_sirae.usuarios.api.router import router_usuarios
from apps_sirae.usuarios.api.views import (
    CustomTokenRefreshView,
    LoginView,
    LogoutView,
    RegistroView,
)


urlpatterns = [
    path('', include(router_usuarios.urls)),

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
]
