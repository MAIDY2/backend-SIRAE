from rest_framework.routers import DefaultRouter

from .views import AsistenciaDiariaViewSet


router_asistencia_diaria = DefaultRouter()

router_asistencia_diaria.register(
    'asistencia-diaria',
    AsistenciaDiariaViewSet,
    basename='asistencia-diaria'
)