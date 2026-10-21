from rest_framework import viewsets

from ..models import RecetaComponente
from .serializer import RecetaComponenteSerializer


class RecetaComponenteViewSet(viewsets.ModelViewSet):
    queryset = RecetaComponente.objects.all()
    serializer_class = RecetaComponenteSerializer
