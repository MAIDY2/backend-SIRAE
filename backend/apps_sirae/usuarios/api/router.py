from rest_framework.routers import DefaultRouter
from .views import UsuarioViewSet, RolViewSet

router = DefaultRouter()

router.register(r'usuarios', UsuarioViewSet, basename='usuarios')
router.register(r'roles', RolViewSet, basename='roles')