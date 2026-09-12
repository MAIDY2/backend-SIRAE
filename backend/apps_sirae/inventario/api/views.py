from rest_framework.viewsets import ModelViewSet
from .serializer import InventarioSerializer
from ..models import Inventario

class InventarioApiViewSet(ModelViewSet):
    serializer_class = InventarioSerializer
    queryset = Inventario.objects.all()