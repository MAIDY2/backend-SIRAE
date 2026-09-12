from rest_framework.routers import DefaultRouter
from .view import IngredienteApiViewset


router_ingredientes = DefaultRouter()

router_ingredientes.register(
    prefix='ingredientes',
    viewset=IngredienteApiViewset,
    basename='ingredientes'
)

urlpatterns = [
]
