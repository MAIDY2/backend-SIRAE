from rest_framework.routers import DefaultRouter
from apps_sirae.platos.api.views import PlatoApiViewSet


router_platos = DefaultRouter()
router_platos.register(
    prefix='platos',
    viewset=PlatoApiViewSet,
    basename='platos'
)