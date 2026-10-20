from rest_framework import viewsets

from ..models import Institucion
from .serializers import InstitucionSerializer


class InstitucionViewSet(viewsets.ModelViewSet):
  queryset = Institucion.objects.all()
  serializer_class = InstitucionSerializer