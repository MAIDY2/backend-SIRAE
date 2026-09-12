from rest_framework.routers import DefaultRouter

from apps_sirae.usuarios.api.views import UsuarioViewSet


router_usuarios = DefaultRouter()

router_usuarios.register(
    r'usuarios',
    UsuarioViewSet,
    basename='usuarios'
)