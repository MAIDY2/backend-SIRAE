from rest_framework import viewsets
from ..models import Sede
from .serializers import SedeSerializer


class SedeViewSet(viewsets.ModelViewSet):
  queryset = Sede.objects.all()
  serializer_class = SedeSerializer

  def get_queryset(self):
    queryset = super().get_queryset()
    institucion_id = self.request.query_params.get('id_institucion')
    if institucion_id:
      queryset = queryset.filter(id_institucion=institucion_id)
    return queryset