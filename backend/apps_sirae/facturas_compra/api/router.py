from rest_framework.routers import DefaultRouter
from .views import FacturaCompraViewSet, InventarioCentralViewSet, ProveedorViewSet

router_facturas_compra = DefaultRouter()
router_facturas_compra.register(
    prefix='facturas-compra',
    viewset=FacturaCompraViewSet,
    basename='facturas-compra'
)
router_facturas_compra.register(
    prefix='inventario-central',
    viewset=InventarioCentralViewSet,
    basename='inventario-central'
)
router_facturas_compra.register(
    prefix='proveedores',
    viewset=ProveedorViewSet,
    basename='proveedores'
)

