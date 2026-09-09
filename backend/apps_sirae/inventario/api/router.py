from rest_framework.routers import DefaultRouter

from apps_sirae.inventario.api.views import (
    CategoriaInventarioApiViewSet,
    UnidadMedidaApiViewSet,
    IngredienteApiViewSet,
    InventarioApiViewSet,
    MovimientoInventarioApiViewSet
    , UserApiViewSet
)


router_inventario = DefaultRouter()


router_inventario.register(
    prefix="categorias",
    viewset=CategoriaInventarioApiViewSet,
    basename="categorias"
)

router_inventario.register(
    prefix="unidades",
    viewset=UnidadMedidaApiViewSet,
    basename="unidades"
)

router_inventario.register(
    prefix="ingredientes",
    viewset=IngredienteApiViewSet,
    basename="ingredientes"
)

router_inventario.register(
    prefix="productos",
    viewset=IngredienteApiViewSet,
    basename="productos"
)

router_inventario.register(
    prefix="inventario",
    viewset=InventarioApiViewSet,
    basename="inventario"
)

router_inventario.register(
    prefix="movimientos",
    viewset=MovimientoInventarioApiViewSet,
    basename="movimientos"
)

router_inventario.register(
    prefix="users",
    viewset=UserApiViewSet,
    basename="users"
)