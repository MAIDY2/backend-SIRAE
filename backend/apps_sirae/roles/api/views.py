from rest_framework import viewsets

from apps_sirae.roles.models import Rol
from apps_sirae.roles.api.serializers import RolSerializer


class RolViewSet(viewsets.ModelViewSet):
    queryset = Rol.objects.all()
    serializer_class = RolSerializer