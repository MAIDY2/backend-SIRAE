from rest_framework.viewsets import ModelViewSet
from apps_sirae.secciones_menu.api.serializer import SeccionMenuSerializer
from apps_sirae.secciones_menu.models import SeccionMenu


class SeccionMenuApiViewSet(ModelViewSet):
    serializer_class = SeccionMenuSerializer
    queryset = SeccionMenu.objects.all().order_by('nombre')