from rest_framework import viewsets

from .models import ContratoSeccionMenu
from .api.serializers import ContratoSeccionMenuSerializer


class ContratoSeccionMenuViewSet(viewsets.ModelViewSet):
    queryset = ContratoSeccionMenu.objects.all()
    serializer_class = ContratoSeccionMenuSerializer