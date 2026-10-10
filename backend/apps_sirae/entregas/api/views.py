from rest_framework import viewsets
from ..models import Entrega
from .serializer import EntregaSerializer
from apps_sirae.usuarios.permissions import IsSupervisorOrAdminRole


class entregasApiViewset(viewsets.ModelViewSet):
    queryset = Entrega.objects.all().order_by('-fecha_entrega', '-id_entrega')
    serializer_class = EntregaSerializer
    permission_classes = [IsSupervisorOrAdminRole]

    def perform_create(self, serializer):
        serializer.save(id_usuario_supervisor=self.request.user.id_usuario)