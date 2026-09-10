from rest_framework.routers import DefaultRouter
from apps_sirae.secciones_menu.api.views import SeccionMenuApiViewSet


router_secciones_menu = DefaultRouter()
router_secciones_menu.register(
    prefix='secciones-menu',
    viewset=SeccionMenuApiViewSet,
    basename='secciones-menu'
)