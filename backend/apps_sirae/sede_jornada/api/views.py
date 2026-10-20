from rest_framework import viewsets
from ..models import SedeJornada
from .serializers import SedeJornadaSerializer


class SedeJornadaViewSet(viewsets.ModelViewSet):
  queryset = SedeJornada.objects.all()
  serializer_class = SedeJornadaSerializer

  def get_queryset(self):
    queryset = super().get_queryset()
    sede_id = self.request.query_params.get('id_sede')
    if sede_id:
      queryset = queryset.filter(id_sede=sede_id)
    return queryset