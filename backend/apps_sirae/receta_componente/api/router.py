from rest_framework.routers import DefaultRouter

from .views import RecetaComponenteViewSet


router_receta_componente = DefaultRouter()

router_receta_componente.register(
    prefix='receta-componentes',
    viewset=RecetaComponenteViewSet,
    basename='receta-componentes'
)
