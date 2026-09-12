from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from apps_sirae.preparacion_asignada.models import PreparacionAsignada

# AQUÍ ESTÁ EL TRUCO: Usamos .serializer (sin S) para que coincida con tu archivo
from .serializer import PreparacionAsignadaSerializer

class PreparacionAsignadaApiViewSet(viewsets.ModelViewSet):
    queryset = PreparacionAsignada.objects.all().order_by('-fecha', '-id_preparacion_asignada')
    serializer_class = PreparacionAsignadaSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_queryset(self):
        queryset = super().get_queryset()
        query_params = self.request.query_params

        filters = {
            'estado_preparacion': query_params.get('estado') or query_params.get('estado_preparacion'),
            'id_menu': query_params.get('id_menu'),
            'id_plato': query_params.get('id_plato'),
            'id_usuario_manipuladora': query_params.get('id_usuario_manipuladora'),
            'id_turno': query_params.get('id_turno'),
            'fecha': query_params.get('fecha'),
        }
        return queryset.filter(**{
            field: value for field, value in filters.items() if value not in (None, '')
        })