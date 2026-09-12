from rest_framework.viewsets import ReadOnlyModelViewSet
from .serializer import SeccionMenuSerializer
from ..models import SeccionMenu


class SeccionMenuApiViewSet(ReadOnlyModelViewSet):
    serializer_class = SeccionMenuSerializer
<<<<<<< HEAD
    queryset = SeccionMenu.objects.all()
=======
    queryset = SeccionMenu.objects.all().order_by('nombre_seccion')
>>>>>>> f7be33e5f87ff6d750f1ab487464488a2fc533ad
