from rest_framework.viewsets import ModelViewSet
from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.unidades_medida.api.serializer import UnidadMedidaSerializer


class UnidadMedidaApiViewSet(ModelViewSet):
    serializer_class = UnidadMedidaSerializer
    queryset = UnidadMedida.objects.all()