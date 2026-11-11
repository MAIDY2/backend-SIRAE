from rest_framework.viewsets import ModelViewSet

from ..models import CategoriaInventario
from .serializer import CategoriaInventarioSerializer
from apps_sirae.usuarios.permissions import IsSuperAdminOrReadOnly


class CategoriaInventarioApiViewSet(ModelViewSet):
    serializer_class = CategoriaInventarioSerializer
    queryset = CategoriaInventario.objects.all()
    permission_classes = [IsSuperAdminOrReadOnly]