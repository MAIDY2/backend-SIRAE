from rest_framework.routers import DefaultRouter

from .views import notificacionesApiViewset

router_notificaciones = DefaultRouter()
router_notificaciones.register(
	prefix='notificaciones',
	viewset=notificacionesApiViewset,
	basename='notificacion',
)