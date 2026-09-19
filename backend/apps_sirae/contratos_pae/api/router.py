from rest_framework.routers import DefaultRouter

from .views import ContratoViewSet

router_contratos = DefaultRouter()
router_contratos.register(
    prefix='contratos',
    viewset=ContratoViewSet,
    basename='contratos',
)
