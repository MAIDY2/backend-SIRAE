
from rest_framework.viewsets import ModelViewSet
from rest_framework.viewsets import ReadOnlyModelViewSet
from django.contrib.auth.models import User

from apps_sirae.inventario.models import (
    CategoriaInventario,
    UnidadMedida,
    Ingrediente,
    Inventario,
    MovimientoInventario
)

from apps_sirae.inventario.api.serializer import (
    CategoriaInventarioSerializer,
    UnidadMedidaSerializer,
    IngredienteSerializer,
    InventarioSerializer,
    MovimientoInventarioSerializer
    , UserSerializer
)


class UserApiViewSet(ReadOnlyModelViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.filter(is_active=True).order_by('username')


class CategoriaInventarioApiViewSet(ModelViewSet):
    serializer_class = CategoriaInventarioSerializer
    queryset = CategoriaInventario.objects.all()


class UnidadMedidaApiViewSet(ModelViewSet):
    serializer_class = UnidadMedidaSerializer
    queryset = UnidadMedida.objects.all()


class IngredienteApiViewSet(ModelViewSet):
    serializer_class = IngredienteSerializer
    queryset = Ingrediente.objects.all()


class InventarioApiViewSet(ModelViewSet):
    serializer_class = InventarioSerializer
    queryset = Inventario.objects.all()


class MovimientoInventarioApiViewSet(ModelViewSet):
    serializer_class = MovimientoInventarioSerializer
    queryset = MovimientoInventario.objects.all()

