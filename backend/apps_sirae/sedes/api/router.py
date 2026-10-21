from rest_framework.routers import DefaultRouter
from .views import SedeViewSet

router = DefaultRouter()
router.register(
                prefix ='sedes', 
                viewset=SedeViewSet, 
                basename='sedes')

urlpatterns = router.urls