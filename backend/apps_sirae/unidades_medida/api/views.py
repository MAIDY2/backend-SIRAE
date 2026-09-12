from rest_framework.viewsets import ModelViewSet
<<<<<<< HEAD
from .serializer import UnidadMedidaSerializer
from ..models import UnidadMedida
=======
from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.unidades_medida.api.serializer import UnidadMedidaSerializer
>>>>>>> f7be33e5f87ff6d750f1ab487464488a2fc533ad


class UnidadMedidaApiViewSet(ModelViewSet):
    serializer_class = UnidadMedidaSerializer
    queryset = UnidadMedida.objects.all()