from rest_framework.viewsets import ModelViewSet

from .models import pasospreparacion
from .serializers import PasosPreparacionSerializer
from apps_sirae.usuarios.permissions import IsJefaSupervisorOrAdminRole


class PasosPreparacionViewSet(ModelViewSet):
	queryset = pasospreparacion.objects.all()
	serializer_class = PasosPreparacionSerializer
	permission_classes = [IsJefaSupervisorOrAdminRole]
