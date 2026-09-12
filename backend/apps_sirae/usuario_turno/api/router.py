from rest_framework.routers import DefaultRouter
from .view import UsuarioTurnoApiViewset


router_usuario_turno = DefaultRouter()

router_usuario_turno.register(
    prefix='usuario-turno',
    viewset=UsuarioTurnoApiViewset,
    basename='usuario-turno'
)

urlpatterns = [
]