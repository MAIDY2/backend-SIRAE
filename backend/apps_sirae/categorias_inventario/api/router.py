from rest_framework.routers import DefaultRouter

from .views import CategoriaInventarioApiViewSet


router_categorias = DefaultRouter()

router_categorias.register(
    prefix='categorias_inventario',
    viewset=CategoriaInventarioApiViewSet,
    basename='categorias_inventario'
)

urlpatterns = []
