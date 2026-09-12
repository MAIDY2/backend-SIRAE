from rest_framework import viewsets
from apps_sirae.usuario_turno.api.serializers import UsuarioTurnoSerializer
from apps_sirae.usuario_turno.models import UsuarioTurno

class UsuarioTurnoApiViewset(viewsets.ModelViewSet):
    queryset = UsuarioTurno.objects.all()
    serializer_class = UsuarioTurnoSerializer
