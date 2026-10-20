from rest_framework.routers import DefaultRouter

from .views import MenuApiViewSet


router_menus = DefaultRouter()

router_menus.register(
    prefix='menus',
    viewset=MenuApiViewSet,
    basename='menus'
)
