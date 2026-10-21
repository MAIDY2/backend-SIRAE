from rest_framework.routers import DefaultRouter
from .views import SedeJornadaViewSet

router = DefaultRouter()
router.register(r'sede-jornadas', SedeJornadaViewSet, basename='sede-jornadas')

urlpatterns = router.urls