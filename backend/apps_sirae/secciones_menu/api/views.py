from rest_framework.viewsets import ModelViewSet

from ..models import SeccionMenu
from .serializer import SeccionMenuSerializer


class SeccionMenuApiViewSet(ModelViewSet):
    serializer_class = SeccionMenuSerializer
    queryset = SeccionMenu.objects.all().order_by('nombre_seccion')
