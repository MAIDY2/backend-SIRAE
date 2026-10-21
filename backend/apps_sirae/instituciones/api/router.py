from rest_framework.routers import DefaultRouter
from .views import InstitucionViewSet, SupervisorInstitucionViewSet

router = DefaultRouter()
router.register(
    prefix='instituciones',
    viewset=InstitucionViewSet,
    basename='instituciones'
)
router.register(
    prefix='supervisor-instituciones',
    viewset=SupervisorInstitucionViewSet,
    basename='supervisor-instituciones'
)

urlpatterns = router.urls