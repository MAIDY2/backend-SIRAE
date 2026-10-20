from rest_framework import viewsets
from .ingredientes.models import Ingrediente
from .ingredientes.serializers import IngredienteSerializer
class IngredienteViewSet(viewsets.ModelViewSet):
    queryset = Ingrediente.objects.all()
    serializer_class = IngredienteSerializer