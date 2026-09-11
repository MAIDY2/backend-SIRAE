from rest_framework.viewsets import ModelViewSet
from ..models import Jornada
from .serializer import JornadaSerializer


class JornadaApiViewSet(ModelViewSet):

    serializer_class = JornadaSerializer
    queryset = Jornada.objects.all()
