from rest_framework.viewsets import ModelViewSet

from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.unidades_medida.api.serializer import UnidadMedidaSerializer
from apps_sirae.usuarios.permissions import IsSuperAdminOrReadOnly


class UnidadMedidaApiViewSet(ModelViewSet):
    serializer_class = UnidadMedidaSerializer
    queryset = UnidadMedida.objects.all()
    permission_classes = [IsSuperAdminOrReadOnly]