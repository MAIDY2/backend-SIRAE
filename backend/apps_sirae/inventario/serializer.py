from rest_framework import serializers

from .models import (
    CategoriaInventario,
    UnidadMedida,
    Ingrediente,
    Inventario,
    MovimientoInventario
)


class CategoriaInventarioSerializer(serializers.ModelSerializer):

    class Meta:
        model = CategoriaInventario
        fields = '__all__'


class UnidadMedidaSerializer(serializers.ModelSerializer):

    class Meta:
        model = UnidadMedida
        fields = '__all__'


class IngredienteSerializer(serializers.ModelSerializer):

    nombre_categoria = serializers.CharField(
        source='id_categoria_inventario.nombre_categoria',
        read_only=True
    )

    nombre_unidad = serializers.CharField(
        source='id_unidad_medida.nombre',
        read_only=True
    )

    class Meta:
        model = Ingrediente
        fields = [
            'id_ingrediente',
            'id_categoria_inventario',
            'nombre_categoria',
            'id_unidad_medida',
            'nombre_unidad',
            'nombre_ingrediente',
            'descripcion',
            'imagen_ingrediente',
            'marca_ingrediente'
        ]


class InventarioSerializer(serializers.ModelSerializer):

    nombre_ingrediente = serializers.CharField(
        source='id_ingrediente.nombre_ingrediente',
        read_only=True
    )

    nombre_unidad = serializers.CharField(
        source='id_unidad_medida.nombre',
        read_only=True
    )

    class Meta:
        model = Inventario
        fields = [
            'id_inventario',
            'id_ingrediente',
            'nombre_ingrediente',
            'cantidad_actual',
            'stock_minimo',
            'id_unidad_medida',
            'nombre_unidad'
        ]


class MovimientoInventarioSerializer(serializers.ModelSerializer):

    nombre_ingrediente = serializers.CharField(
        source='id_ingrediente.nombre_ingrediente',
        read_only=True
    )

    class Meta:
        model = MovimientoInventario
        fields = [
            'id_movimiento_inventario',
            'id_ingrediente',
            'nombre_ingrediente',
            'id_usuario_manipuladora',
            'tipo_movimiento',
            'fecha',
            'cantidad',
            'observaciones',
            'id_unidad_medida'
        ]