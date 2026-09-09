from rest_framework.routers import DefaultRouter

from .views import movimientos_inventarioApiViewset

router_movimientos_inventario = DefaultRouter()
router_movimientos_inventario.register(
	prefix='',
	viewset=movimientos_inventarioApiViewset,
	basename='movimiento-inventario',
)