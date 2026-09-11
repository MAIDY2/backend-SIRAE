from rest_framework.viewsets import ReadOnlyModelViewSet
from .serializer import SeccionMenuSerializer
from ..models import SeccionMenu


class SeccionMenuApiViewSet(ReadOnlyModelViewSet):
    serializer_class = SeccionMenuSerializer
    queryset = SeccionMenu.objects.all()