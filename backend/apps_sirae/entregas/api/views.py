from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from ..models import Entrega
from .serializer import EntregaSerializer


class entregasApiViewset(viewsets.ModelViewSet):
    queryset = Entrega.objects.all().order_by('-fecha_entrega', '-id_entrega')
    serializer_class = EntregaSerializer
    permission_classes = [IsAuthenticated]