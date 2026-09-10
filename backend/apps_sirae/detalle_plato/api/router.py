from rest_framework.routers import DefaultRouter
from apps_sirae.detalle_plato.api.views import DetallePlatoApiViewSet


router_detalle_plato = DefaultRouter()
router_detalle_plato.register(
    prefix='detalle-plato',
    viewset=DetallePlatoApiViewSet,
    basename='detalle-plato'
)