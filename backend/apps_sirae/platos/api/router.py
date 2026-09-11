from rest_framework.routers import DefaultRouter
from .views import PlatoApiViewSet

router_platos = DefaultRouter()
router_platos.register(
    prefix="platos",
    viewset=PlatoApiViewSet,
    basename="platos"
)

urlpatterns = []