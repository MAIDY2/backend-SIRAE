from rest_framework.routers import DefaultRouter
from apps_sirae.unidades_medida.api.views import UnidadMedidaApiViewSet


router_unidades_medida = DefaultRouter()
router_unidades_medida.register(
    prefix='unidades_medida',
    viewset=UnidadMedidaApiViewSet,
    basename='unidades_medida'
)