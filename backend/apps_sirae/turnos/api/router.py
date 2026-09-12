from rest_framework.routers import DefaultRouter
from .view import TurnoApiViewset


router_turnos = DefaultRouter()

router_turnos.register(
    prefix='turnos',
    viewset=TurnoApiViewset,
    basename='turnos'
)

urlpatterns = [
]