from rest_framework.routers import DefaultRouter
from .views import GradosApiViewSet, GrupoGramajeApiViewSet

router_grados = DefaultRouter()
router_grados.register(
    prefix="grados",
    viewset=GradosApiViewSet,
    basename="grados"
)
router_grados.register(
    prefix="grupos-gramaje",
    viewset=GrupoGramajeApiViewSet,
    basename="grupos_gramaje"
)

router_grados_without_slash = DefaultRouter(trailing_slash=False)
router_grados_without_slash.register(
    prefix="grados",
    viewset=GradosApiViewSet,
    basename="grados_without_slash"
)
router_grados_without_slash.register(
    prefix="grupos-gramaje",
    viewset=GrupoGramajeApiViewSet,
    basename="grupos_gramaje_without_slash"
)

urlPatterns = []