from rest_framework.routers import DefaultRouter
from .views import RolViewSet

router = DefaultRouter()
router.register(r'roles', RolViewSet, basename='rol')
