from rest_framework.viewsets import ModelViewSet

from ..models import CategoriaInventario
from .serializer import CategoriaInventarioSerializer


class CategoriaInventarioApiViewSet(ModelViewSet):

    serializer_class = CategoriaInventarioSerializer
    queryset = CategoriaInventario.objects.all()
