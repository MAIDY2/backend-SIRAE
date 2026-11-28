from rest_framework import viewsets

from ..models import RecetaComponente
from .serializer import RecetaComponenteSerializer
from apps_sirae.usuarios.permissions import IsJefaSupervisorOrAdminRole


class RecetaComponenteViewSet(viewsets.ModelViewSet):
    queryset = RecetaComponente.objects.select_related('id_ingrediente').all()
    serializer_class = RecetaComponenteSerializer
    permission_classes = [IsJefaSupervisorOrAdminRole]
