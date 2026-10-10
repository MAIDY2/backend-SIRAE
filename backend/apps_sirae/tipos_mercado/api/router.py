from rest_framework.routers import DefaultRouter
from apps_sirae.tipos_mercado.api.views import TipoMercadoViewSet

router_tipos_mercado = DefaultRouter()
router_tipos_mercado.register(
    prefix='tipos-mercado',
    viewset=TipoMercadoViewSet, 
    basename='tipos_mercado')