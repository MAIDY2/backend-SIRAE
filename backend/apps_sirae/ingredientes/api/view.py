from rest_framework import viewsets
from apps_sirae.ingredientes.api.serializers import IngredienteSerializer
from apps_sirae.ingredientes.models import Ingrediente

class IngredienteApiViewset(viewsets.ModelViewSet):
    queryset = Ingrediente.objects.all()
    serializer_class = IngredienteSerializer
