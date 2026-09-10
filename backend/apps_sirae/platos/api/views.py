from rest_framework.viewsets import ModelViewSet
from apps_sirae.platos.api.serializer import PlatoSerializer
from apps_sirae.platos.models import Plato


class PlatoApiViewSet(ModelViewSet):
    serializer_class = PlatoSerializer
    queryset = Plato.objects.all().select_related('id_seccion_menu').order_by('nombre')