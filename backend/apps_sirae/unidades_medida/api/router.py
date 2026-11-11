from rest_framework.routers import DefaultRouter
from .views import EquivalenciaUnidadApiViewSet, UnidadMedidaApiViewSet

router_unidades_medida = DefaultRouter()
router_unidades_medida.register(
    prefix="unidades_medida",
    viewset=UnidadMedidaApiViewSet,
    basename="unidades_medida"
)
router_unidades_medida.register(
    prefix="equivalencias-unidad",
    viewset=EquivalenciaUnidadApiViewSet,
    basename="equivalencias_unidad"
)

urlpatterns = []
