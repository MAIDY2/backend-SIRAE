from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from ..models import Notificacion
from .serializer import NotificacionSerializer


class notificacionesApiViewset(viewsets.ModelViewSet):
    queryset = Notificacion.objects.all().order_by('-fecha_hora', '-id_notificacion')
    serializer_class = NotificacionSerializer
    permission_classes = [IsAuthenticated]