from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet
from ..models import DetallePlato
from .serializer import DetallePlatoSerializer


class DetallePlatoApiViewSet(ModelViewSet):
    serializer_class = DetallePlatoSerializer
    queryset = DetallePlato.objects.all()
    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ['get']