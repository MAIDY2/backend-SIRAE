from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from ..models import AsistenciaDiaria
from .serializer import AsistenciaDiariaSerializer
from apps_sirae.usuarios.permissions import IsJefaRole


class AsistenciaDiariaViewSet(viewsets.ModelViewSet):

    queryset = AsistenciaDiaria.objects.all().order_by(
        '-fecha',
        '-id_asistencia'
    )

    serializer_class = AsistenciaDiariaSerializer

    def get_permissions(self):

        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]

        return [IsJefaRole()]

    def perform_create(self, serializer):
        serializer.save(id_usuario_manipuladora=self.request.user.id_usuario)

    def perform_update(self, serializer):
        serializer.save(id_usuario_manipuladora=self.request.user.id_usuario)