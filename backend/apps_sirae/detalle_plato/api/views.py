from rest_framework.viewsets import ModelViewSet
from apps_sirae.detalle_plato.api.serializer import DetallePlatoSerializer
from apps_sirae.detalle_plato.models import DetallePlato


class DetallePlatoApiViewSet(ModelViewSet):
    serializer_class = DetallePlatoSerializer
    queryset = DetallePlato.objects.all()