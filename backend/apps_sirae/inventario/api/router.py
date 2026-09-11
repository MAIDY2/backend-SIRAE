from rest_framework.routers import DefaultRouter
from .views import InventarioApiViewSet

router_inventario = DefaultRouter()

router_inventario.register(
    prefix="inventario",
    viewset=InventarioApiViewSet,
    basename="inventario"
)

urlPatterns = []