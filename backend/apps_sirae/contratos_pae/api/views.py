from rest_framework.viewsets import ModelViewSet


from ..models import Contrato
from .serializer import ContratoSerializer



class ContratoViewSet(ModelViewSet):
    serializer_class = ContratoSerializer
    queryset = Contrato.objects.all()





