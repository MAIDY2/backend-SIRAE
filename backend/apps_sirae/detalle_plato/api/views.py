from rest_framework.viewsets import ReadOnlyModelViewSet
from .serializer import DetallePlatoSerializer
from ..models import DetallePlato


class DetallePlatoApiViewSet(ReadOnlyModelViewSet):
    serializer_class = DetallePlatoSerializer
    queryset = DetallePlato.objects.all()