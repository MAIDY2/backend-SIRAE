from django.contrib import admin
from django.urls import include, path

from apps_sirae.inventario.api.router import router_inventario
from apps_sirae.usuarios.api.password_reset import (
    CambiarPasswordView,
    ConfirmarRecuperacionPasswordView,
    PerfilUsuarioView,
    SolicitarRecuperacionPasswordView,
    ValidarTokenPasswordView,
)
from apps_sirae.usuarios.api.router import router
from apps_sirae.usuarios.api.serializers import CustomTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Autenticación y Tokens
    path('api/login/', TokenObtainPairView.as_view(serializer_class=CustomTokenObtainPairSerializer), name='token_obtain_pair'),
    path('api/auth/login/', TokenObtainPairView.as_view(serializer_class=CustomTokenObtainPairSerializer), name='auth_login'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='auth_token_refresh'),

    # Perfil y Cambio de Contraseña (usuario autenticado)
    path('api/auth/me/', PerfilUsuarioView.as_view(), name='auth_me'),
    path('api/auth/cambiar-password/', CambiarPasswordView.as_view(), name='auth_cambiar_password'),

    # Recuperación de Contraseña (sin sesión activa)
    path('api/auth/password-reset/solicitar/', SolicitarRecuperacionPasswordView.as_view(), name='password_reset_solicitar'),
    path('api/auth/password-reset/validar-token/', ValidarTokenPasswordView.as_view(), name='password_reset_validar_token'),
    path('api/auth/password-reset/confirmar/', ConfirmarRecuperacionPasswordView.as_view(), name='password_reset_confirmar'),

    # Enrutadores
    path('api/', include(router.urls)),
    path('api/', include(router_inventario.urls)),
]
