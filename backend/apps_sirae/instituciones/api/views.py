from rest_framework import viewsets

from ..models import Institucion
from .serializers import InstitucionSerializer
from apps_sirae.usuarios.permissions import IsSuperAdminOrReadOnly


class InstitucionViewSet(viewsets.ModelViewSet):
    queryset = Institucion.objects.all()
    serializer_class = InstitucionSerializer
    permission_classes = [IsSuperAdminOrReadOnly]