from rest_framework.viewsets import ModelViewSet
from apps_sirae.unidades_medida.api.serializer import UnidadMedidaSerializer
from apps_sirae.unidades_medida.models import UnidadMedida


class UnidadMedidaApiViewSet(ModelViewSet):
    serializer_class = UnidadMedidaSerializer
    queryset = UnidadMedida.objects.all().order_by('nombre')