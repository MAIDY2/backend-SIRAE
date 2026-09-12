from rest_framework.routers import DefaultRouter
from .views import GradosApiViewSet

router_grados = DefaultRouter()
router_grados.register(
    prefix="grados",
    viewset=GradosApiViewSet,
    basename="grados"
)

router_grados_without_slash = DefaultRouter(trailing_slash=False)
router_grados_without_slash.register(
    prefix="grados",
    viewset=GradosApiViewSet,
    basename="grados_without_slash"
)

urlPatterns = []