<<<<<<< HEAD
from rest_framework.viewsets import ReadOnlyModelViewSet
from .serializer import PlatoSerializer
from ..models import Plato
=======
from rest_framework.viewsets import ModelViewSet
from apps_sirae.platos.models import Plato
from apps_sirae.platos.api.serializer import PlatoSerializer
>>>>>>> f7be33e5f87ff6d750f1ab487464488a2fc533ad


class PlatoApiViewSet(ReadOnlyModelViewSet):
    serializer_class = PlatoSerializer
<<<<<<< HEAD
    queryset = Plato.objects.all()
=======
    queryset = Plato.objects.all().select_related('id_seccion').order_by('nombre_plato')
>>>>>>> f7be33e5f87ff6d750f1ab487464488a2fc533ad
