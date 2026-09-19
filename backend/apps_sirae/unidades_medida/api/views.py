from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny # <--- 1. Importa esto
from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.unidades_medida.api.serializer import UnidadMedidaSerializer


class UnidadMedidaApiViewSet(ModelViewSet):
    serializer_class = UnidadMedidaSerializer
    queryset = UnidadMedida.objects.all()
    permission_classes = [AllowAny] # <--- 2. Agrégalo aquí para quitar el requisito de login temporalmente