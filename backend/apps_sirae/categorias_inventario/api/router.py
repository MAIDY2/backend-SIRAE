from rest_framework.routers import DefaultRouter

from .views import CategoriaInventarioApiViewSet


router_categorias = DefaultRouter()

router_categorias.register(
    prefix='',
    viewset=CategoriaInventarioApiViewSet,
    basename='categorias-inventario'
)
