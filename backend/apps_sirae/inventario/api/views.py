from rest_framework.viewsets import ModelViewSet
from .serializer import InventarioSerializer
from ..models import Inventario
from apps_sirae.usuarios.permissions import IsSupervisorOrAdminRole

class InventarioApiViewSet(ModelViewSet):
    serializer_class = InventarioSerializer
    queryset = Inventario.objects.all()
    permission_classes = [IsSupervisorOrAdminRole]