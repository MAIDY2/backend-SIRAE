from rest_framework.viewsets import ModelViewSet
from .serializer import GramageSerializer
from ..models import Gramage

class GramageApiViewSet(ModelViewSet):
    serializer_class = GramageSerializer
    queryset = Gramage.objects.all()