from rest_framework.routers import DefaultRouter

from apps_sirae.salidas_inventario.api.views import SalidaInventarioApiViewSet


router_salidas_inventario = DefaultRouter()

router_salidas_inventario.register(
    r'salidas-inventario',
    SalidaInventarioApiViewSet,
    basename='salidas-inventario'
)