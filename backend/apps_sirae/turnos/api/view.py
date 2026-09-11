from rest_framework import viewsets
from apps_sirae.turnos.api.serializers import TurnoSerializer
from apps_sirae.turnos.models import Turno

class TurnoApiViewset(viewsets.ModelViewSet):
    queryset = Turno.objects.all()
    serializer_class = TurnoSerializer
