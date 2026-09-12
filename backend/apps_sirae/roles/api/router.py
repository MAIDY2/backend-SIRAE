from rest_framework.routers import DefaultRouter

from apps_sirae.roles.api.views import RolViewSet


router_roles = DefaultRouter()
router_roles.register(r'roles', RolViewSet, basename='roles')