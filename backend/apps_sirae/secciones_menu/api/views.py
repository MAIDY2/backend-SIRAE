from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny

from ..models import SeccionMenu
from .serializer import SeccionMenuSerializer


class SeccionMenuApiViewSet(ModelViewSet):
    serializer_class = SeccionMenuSerializer
    queryset = SeccionMenu.objects.all().order_by('nombre_seccion')
    permission_classes = [AllowAny]
    authentication_classes = []
