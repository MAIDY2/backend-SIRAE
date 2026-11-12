from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps_sirae.reportes.api.views import (
    PlanillaGeneradaViewSet,
    PlantillaOficialViewSet,
    PlantillasOperativasDatosAPIView,
    ReportesConsolidadosAPIView,
)

router_reportes = DefaultRouter()
router_reportes.register(r'reportes/plantillas', PlantillaOficialViewSet, basename='reportes-plantillas')
router_reportes.register(r'reportes/planillas', PlanillaGeneradaViewSet, basename='reportes-planillas')

urlpatterns = [
    path('', include(router_reportes.urls)),
    path('reportes/consolidados/', ReportesConsolidadosAPIView.as_view(), name='reportes-consolidados'),
    path(
        'reportes/plantillas-operativas/datos/',
        PlantillasOperativasDatosAPIView.as_view(),
        name='reportes-plantillas-operativas-datos',
    ),
]

