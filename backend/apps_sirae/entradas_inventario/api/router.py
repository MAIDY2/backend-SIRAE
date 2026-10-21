from rest_framework.routers import DefaultRouter

from apps_sirae.entradas_inventario.api.views import EntradaInventarioApiViewSet


router_entradas_inventario = DefaultRouter()

router_entradas_inventario.register(
    r'entradas-inventario',
    EntradaInventarioApiViewSet,
    basename='entradas-inventario'
)