from rest_framework.viewsets import ModelViewSet
from .serializer import GradosSerializer
from ..models import Grados

class GradosApiViewSet(ModelViewSet):
    serializer_class = GradosSerializer
    queryset = Grados.objects.all()