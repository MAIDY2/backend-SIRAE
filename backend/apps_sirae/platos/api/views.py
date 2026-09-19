from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny

from ..models import Plato
from .serializer import PlatoSerializer


class PlatoApiViewSet(ModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = PlatoSerializer
    queryset = Plato.objects.all().select_related('id_seccion').order_by('nombre_plato')
