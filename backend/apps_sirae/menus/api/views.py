from rest_framework.viewsets import ModelViewSet

from ..models import Menu
from .serializer import MenuSerializer


class MenuApiViewSet(ModelViewSet):

    serializer_class = MenuSerializer
    queryset = Menu.objects.all()
