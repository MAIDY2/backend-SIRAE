from rest_framework.routers import DefaultRouter
from .views import GramageApiViewSet

router_gramage = DefaultRouter()

router_gramage.register(
    prefix="gramage",
    viewset=GramageApiViewSet,
    basename="gramage"
)

router_gramage_without_slash = DefaultRouter(trailing_slash=False)
router_gramage_without_slash.register(
    prefix="gramage",
    viewset=GramageApiViewSet,
    basename="gramage_without_slash"
)

urlPatterns = []