from rest_framework.routers import DefaultRouter

from .views import (
    CategoriaInventarioViewSet,
    UnidadMedidaViewSet,
    IngredienteViewSet,
    InventarioViewSet,
    MovimientoInventarioViewSet
)


router = DefaultRouter()

router.register(
    r'categorias',
    CategoriaInventarioViewSet,
    basename='categorias'
)

router.register(
    r'unidades',
    UnidadMedidaViewSet,
    basename='unidades'
)

router.register(
    r'ingredientes',
    IngredienteViewSet,
    basename='ingredientes'
)

router.register(
    r'inventario',
    InventarioViewSet,
    basename='inventario'
)

router.register(
    r'movimientos',
    MovimientoInventarioViewSet,
    basename='movimientos'
)


urlpatterns = router.urls