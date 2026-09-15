from rest_framework.viewsets import ModelViewSet

from ..models import Plato
from .serializer import PlatoSerializer


class PlatoApiViewSet(ModelViewSet):
    serializer_class = PlatoSerializer
    queryset = Plato.objects.all().select_related('id_seccion').order_by('nombre_plato')
