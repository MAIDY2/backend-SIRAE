from rest_framework.viewsets import ModelViewSet

from apps_sirae.menus.models import Menu
from apps_sirae.menus.api.serializer import MenuSerializer
from apps_sirae.usuarios.permissions import IsJefaOrAdminOrSuperAdminRole


class MenuApiViewSet(ModelViewSet):

    serializer_class = MenuSerializer
    queryset = Menu.objects.all()
    permission_classes = [IsJefaOrAdminOrSuperAdminRole]
