from rest_framework.routers import DefaultRouter
from .views import AsignacionInventarioViewSet, InventarioApiViewSet

router_inventario = DefaultRouter()

router_inventario.register(
    prefix="inventario",
    viewset=InventarioApiViewSet,
    basename="inventario"
)
router_inventario.register(
    prefix="asignaciones-inventario",
    viewset=AsignacionInventarioViewSet,
    basename="asignaciones-inventario"
)

urlPatterns = []