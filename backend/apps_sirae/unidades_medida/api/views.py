from rest_framework.viewsets import ModelViewSet
from .serializer import UnidadMedidaSerializer
from ..models import UnidadMedida


class UnidadMedidaApiViewSet(ModelViewSet):
    serializer_class = UnidadMedidaSerializer
    queryset = UnidadMedida.objects.all()