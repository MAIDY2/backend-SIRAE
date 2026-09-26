from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from ..models import AsistenciaDiaria
from .serializer import AsistenciaDiariaSerializer


class AsistenciaDiariaViewSet(viewsets.ModelViewSet):

    queryset = AsistenciaDiaria.objects.all().order_by(
        '-fecha',
        '-id_asistencia'
    )

    serializer_class = AsistenciaDiariaSerializer

    permission_classes = [IsAuthenticated]