from rest_framework.routers import DefaultRouter
from .views import JornadaApiViewSet

router_jornadas = DefaultRouter()

router_jornadas.register(
    prefix='jornadas',  
    viewset=JornadaApiViewSet,
    basename='jornadas'
)
