
from django.contrib.auth.models import User
from rest_framework import serializers

from apps_sirae.inventario.models import (
    CategoriaInventario,
    UnidadMedida,
    Ingrediente,
    Inventario,
    MovimientoInventario
)


class PercentageDecimalField(serializers.DecimalField):

    def to_internal_value(self, data):
        if data is None or data == '':
            if self.allow_null:
                return None
            raise serializers.ValidationError('This field may not be null.')

        if isinstance(data, str):
            data = data.strip().replace('%', '')
            if data == '':
                if self.allow_null:
                    return None
                raise serializers.ValidationError('This field may not be blank.')

        return super().to_internal_value(data)


class UserSerializer(serializers.ModelSerializer):

    nombre = serializers.SerializerMethodField()
    rol = serializers.SerializerMethodField()
    estado = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'nombre',
            'rol',
            'estado',
            'username',
            'first_name',
            'last_name',
            'email',
            'is_active'
        ]

    def get_nombre(self, obj):
        return obj.get_full_name() or obj.username

    def get_rol(self, obj):
        group = obj.groups.order_by('name').first()
        return group.name if group else 'Admin'

    def get_estado(self, obj):
        return 'Activo' if obj.is_active else 'Inactivo'


class CategoriaInventarioSerializer(serializers.ModelSerializer):

    class Meta:
        model = CategoriaInventario
        fields = [
            'id_categoria_inventario',
            'nombre_categoria'
        ]


class UnidadMedidaSerializer(serializers.ModelSerializer):

    class Meta:
        model = UnidadMedida
        fields = [
            'id_unidad_medida',
            'nombre',
            'abreviatura'
        ]


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

    cantidad_actual = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True
    )

    stock_minimo = PercentageDecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True
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

    class Meta:
        model = MovimientoInventario
        fields = [
            'id_movimiento_inventario',
            'id_ingrediente',
            'id_usuario_manipuladora',
            'tipo_movimiento',
            'fecha',
            'cantidad',
            'observaciones',
            'id_unidad_medida'
        ]

