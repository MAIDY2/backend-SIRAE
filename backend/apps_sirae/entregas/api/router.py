from rest_framework.routers import DefaultRouter

from .views import entregasApiViewset

router_entregas = DefaultRouter()
router_entregas.register(
	prefix='entregas',
	viewset=entregasApiViewset,
	basename='entrega',
)