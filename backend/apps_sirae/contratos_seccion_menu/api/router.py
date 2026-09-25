from rest_framework.routers import DefaultRouter

from apps_sirae.contratos_seccion_menu.views import ContratoSeccionMenuViewSet


router_contrato_seccion_menu = DefaultRouter()

router_contrato_seccion_menu.register(
    r'contratos-secciones-menu',
    ContratoSeccionMenuViewSet,
    basename='contrato-seccion-menu'
)