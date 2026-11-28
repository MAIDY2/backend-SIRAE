from rest_framework.viewsets import ModelViewSet
from ..models import DetallePlato
from .serializer import DetallePlatoSerializer
from apps_sirae.usuarios.permissions import IsJefaSupervisorOrAdminRole


class DetallePlatoApiViewSet(ModelViewSet):
    serializer_class = DetallePlatoSerializer
    queryset = DetallePlato.objects.all()
    permission_classes = [IsJefaSupervisorOrAdminRole]
