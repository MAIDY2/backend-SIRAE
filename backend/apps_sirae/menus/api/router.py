from rest_framework.routers import DefaultRouter

from apps_sirae.menus.api.views import MenuApiViewSet


router_menus = DefaultRouter()

router_menus.register(
    prefix='menus',
    viewset=MenuApiViewSet,
    basename='menus'
)
