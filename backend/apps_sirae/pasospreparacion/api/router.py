from rest_framework.routers import DefaultRouter

from ..views import PasosPreparacionViewSet

router_pasos_preparacion = DefaultRouter()

router_pasos_preparacion.register(
    prefix='',
    viewset=PasosPreparacionViewSet,
    basename='pasos-preparacion',
)
