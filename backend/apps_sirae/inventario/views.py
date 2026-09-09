from django.shortcuts import render
from rest_framework import viewsets


from .models import (
    CategoriaInventario,
    UnidadMedida,
    Ingrediente,
    Inventario,
    MovimientoInventario
)

from .serializer import (
    CategoriaInventarioSerializer,
    UnidadMedidaSerializer,
    IngredienteSerializer,
    InventarioSerializer,
    MovimientoInventarioSerializer
)


class CategoriaInventarioViewSet(viewsets.ModelViewSet):

    queryset = CategoriaInventario.objects.all()
    serializer_class = CategoriaInventarioSerializer


class UnidadMedidaViewSet(viewsets.ModelViewSet):

    queryset = UnidadMedida.objects.all()
    serializer_class = UnidadMedidaSerializer


class IngredienteViewSet(viewsets.ModelViewSet):

    queryset = Ingrediente.objects.select_related(
        'id_categoria_inventario',
        'id_unidad_medida'
    ).all()

    serializer_class = IngredienteSerializer


class InventarioViewSet(viewsets.ModelViewSet):

    queryset = Inventario.objects.select_related(
        'id_ingrediente',
        'id_unidad_medida'
    ).all()

    serializer_class = InventarioSerializer


class MovimientoInventarioViewSet(viewsets.ModelViewSet):

    queryset = MovimientoInventario.objects.select_related(
        'id_ingrediente',
        'id_unidad_medida'
    ).all()

    serializer_class = MovimientoInventarioSerializer