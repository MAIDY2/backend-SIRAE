from rest_framework import viewsets
from ..models import AsistenciaDiaria
from .serializer import AsistenciaDiariaSerializer
from apps_sirae.usuarios.permissions import IsJefaRole


class AsistenciaDiariaViewSet(viewsets.ModelViewSet):

    queryset = AsistenciaDiaria.objects.all().order_by(
        '-fecha',
        '-id_asistencia'
    )

    serializer_class = AsistenciaDiariaSerializer

    permission_classes = [IsJefaRole]

    def perform_create(self, serializer):
        serializer.save(id_usuario_manipuladora=self.request.user.id_usuario)

    def perform_update(self, serializer):
        serializer.save(id_usuario_manipuladora=self.request.user.id_usuario)