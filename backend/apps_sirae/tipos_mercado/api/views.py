from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from apps_sirae.tipos_mercado.models import TipoMercado
from apps_sirae.tipos_mercado.api.serializers import TipoMercadoSerializer

class TipoMercadoViewSet(ModelViewSet):
    queryset = TipoMercado.objects.all()
    serializer_class = TipoMercadoSerializer
    permission_classes = [IsAuthenticated]