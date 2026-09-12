from rest_framework.viewsets import ModelViewSet

from .models import pasospreparacion
from .serializers import PasosPreparacionSerializer


class PasosPreparacionViewSet(ModelViewSet):
	queryset = pasospreparacion.objects.all()
	serializer_class = PasosPreparacionSerializer
