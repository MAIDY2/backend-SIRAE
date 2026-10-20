from rest_framework import viewsets

from apps_sirae.ingredientes.api.serializers import IngredienteSerializer
from apps_sirae.ingredientes.models import Ingrediente


class IngredienteApiViewset(viewsets.ModelViewSet):
    serializer_class = IngredienteSerializer

    def get_queryset(self):
        queryset = Ingrediente.objects.all()
        parametros = self.request.query_params

        # Buscar ingredientes por nombre.
        buscar = (
            parametros.get('buscar')
            or parametros.get('search')
        )

        if buscar:
            queryset = queryset.filter(
                nombre_ingrediente__icontains=buscar.strip()
            )

        # Filtrar por clasificación de conservación.
        tipo = parametros.get('tipo', '').strip().lower()

        if tipo in ('perecedero', 'no_perecedero'):
            queryset = queryset.filter(
                tipo_conservacion=tipo
            )

        return queryset
