from rest_framework.routers import DefaultRouter

from .views import JornadaApiViewSet


router_jornadas = DefaultRouter()

router_jornadas.register(
    prefix='',
    viewset=JornadaApiViewSet,
    basename='jornadas'
)
