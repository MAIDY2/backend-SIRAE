from rest_framework.viewsets import ModelViewSet

from ..models import Menu
from .serializer import MenuSerializer
from apps_sirae.usuarios.permissions import IsJefaOrAdminRole


class MenuApiViewSet(ModelViewSet):

    serializer_class = MenuSerializer
    queryset = Menu.objects.all()
    permission_classes = [IsJefaOrAdminRole]
