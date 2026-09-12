from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from ..models import PreparacionAsignada
from .serializers import PreparacionAsignadaSerializer

class PreparacionAsignadaApiViewSet(viewsets.ModelViewSet):
    queryset = PreparacionAsignada.objects.all()
    serializer_class = PreparacionAsignadaSerializer
    permission_classes = [AllowAny]

PreparacionAsignadaViewSet = PreparacionAsignadaApiViewSet