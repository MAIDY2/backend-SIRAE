from rest_framework.routers import DefaultRouter
from .views import PreparacionAsignadaApiViewSet

router = DefaultRouter()
router.register(prefix='', basename='preparacion-asignada', viewset=PreparacionAsignadaApiViewSet)

urlpatterns = router.urls