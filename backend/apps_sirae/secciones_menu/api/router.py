from rest_framework.routers import DefaultRouter
from .views import SeccionMenuApiViewSet

router_secciones_menu = DefaultRouter()
router_secciones_menu.register(
    prefix="secciones_menu",
    viewset=SeccionMenuApiViewSet,
    basename="secciones_menu"
)

urlpatterns = []