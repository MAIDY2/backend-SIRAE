from rest_framework.viewsets import ModelViewSet
from ..models import DetallePlato
from .serializer import DetallePlatoSerializer


class DetallePlatoApiViewSet(ModelViewSet):
    serializer_class = DetallePlatoSerializer
    queryset = DetallePlato.objects.all()