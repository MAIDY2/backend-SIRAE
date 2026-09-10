from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .router import router
from .serializers import CustomTokenObtainPairSerializer
# Rutas de perfil (opcionales por si se necesitan)
from .password_reset import PerfilUsuarioView

urlpatterns = [
    # 1. Endpoints de Login y JWT
    path('login/', TokenObtainPairView.as_view(serializer_class=CustomTokenObtainPairSerializer), name='token_obtain_pair'),
    path('auth/login/', TokenObtainPairView.as_view(serializer_class=CustomTokenObtainPairSerializer), name='auth_login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='auth_token_refresh'),

    # 2. Perfil de usuario autenticado
    path('auth/me/', PerfilUsuarioView.as_view(), name='auth_me'),
    path('usuarios/me/', PerfilUsuarioView.as_view(), name='usuarios_me'),

    # 3. Router de CRUDs (Usuarios y Roles)
    path('', include(router.urls)),
]
