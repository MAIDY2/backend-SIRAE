from rest_framework.viewsets import ReadOnlyModelViewSet
from .serializer import PlatoSerializer
from ..models import Plato


class PlatoApiViewSet(ReadOnlyModelViewSet):
    serializer_class = PlatoSerializer
    queryset = Plato.objects.all()