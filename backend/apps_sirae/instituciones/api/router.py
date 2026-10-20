from rest_framework.routers import DefaultRouter
from .views import InstitucionViewSet

router = DefaultRouter()
router.register(
    prefix='instituciones',
    viewset=InstitucionViewSet,
    basename='instituciones'
)

urlpatterns = router.urls