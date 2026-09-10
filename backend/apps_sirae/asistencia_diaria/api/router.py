from rest_framework.routers import DefaultRouter

from .views import asistencia_diariaApiViewset

router_asistencia_diaria = DefaultRouter()
router_asistencia_diaria.register(
	prefix='asistencia-diaria',
	viewset=asistencia_diariaApiViewset,
	basename='asistencia-diaria',
)