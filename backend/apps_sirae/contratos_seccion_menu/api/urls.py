from rest_framework.routers import DefaultRouter
from apps_sirae.contratos_seccion_menu.api.views import ContratoSeccionMenuViewSet


router = DefaultRouter()

router.register(
    r'contratos-seccion-menu',
    ContratoSeccionMenuViewSet,
    basename='contratos-seccion-menu'
)

urlpatterns = router.urls