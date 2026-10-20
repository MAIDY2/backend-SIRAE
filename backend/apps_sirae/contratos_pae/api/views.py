from rest_framework.viewsets import ModelViewSet


from ..models import Contrato
from .serializer import ContratoSerializer
from apps_sirae.usuarios.permissions import IsSuperAdminOrReadOnly


class ContratoViewSet(ModelViewSet):
    serializer_class = ContratoSerializer
    queryset = Contrato.objects.all()
    permission_classes = [IsSuperAdminOrReadOnly]





