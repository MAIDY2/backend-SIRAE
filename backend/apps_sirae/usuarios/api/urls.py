from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .router import router
from .serializers import CustomTokenObtainPairSerializer
from .password_reset import (
    SolicitarRecuperacionPasswordView,
    ValidarTokenPasswordView,
    ConfirmarRecuperacionPasswordView,
    CambiarPasswordView,
    PerfilUsuarioView
)

urlpatterns = [
    # 1. Endpoints de Login y JWT
    path('login/', TokenObtainPairView.as_view(serializer_class=CustomTokenObtainPairSerializer), name='token_obtain_pair'),
    path('auth/login/', TokenObtainPairView.as_view(serializer_class=CustomTokenObtainPairSerializer), name='auth_login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='auth_token_refresh'),

    # 2. Perfil y Cambio de Contraseña de usuario autenticado
    path('auth/me/', PerfilUsuarioView.as_view(), name='auth_me'),
    path('usuarios/me/', PerfilUsuarioView.as_view(), name='usuarios_me'),
    path('auth/cambiar-password/', CambiarPasswordView.as_view(), name='auth_cambiar_password'),
    path('usuarios/cambiar-password/', CambiarPasswordView.as_view(), name='usuarios_cambiar_password'),

    # 3. Recuperación de Contraseña (sin sesión activa)
    path('auth/password-reset/solicitar/', SolicitarRecuperacionPasswordView.as_view(), name='password_reset_solicitar'),
    path('auth/password-reset/validar-token/', ValidarTokenPasswordView.as_view(), name='password_reset_validar_token'),
    path('auth/password-reset/confirmar/', ConfirmarRecuperacionPasswordView.as_view(), name='password_reset_confirmar'),

    # Rutas alternativas en español dentro de /usuarios/recuperar-password/
    path('usuarios/recuperar-password/solicitar/', SolicitarRecuperacionPasswordView.as_view(), name='usuarios_recuperar_solicitar'),
    path('usuarios/recuperar-password/validar-token/', ValidarTokenPasswordView.as_view(), name='usuarios_recuperar_validar'),
    path('usuarios/recuperar-password/confirmar/', ConfirmarRecuperacionPasswordView.as_view(), name='usuarios_recuperar_confirmar'),

    # 4. Router de CRUDs (Usuarios y Roles)
    path('', include(router.urls)),
]
