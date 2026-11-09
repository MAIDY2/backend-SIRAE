from rest_framework import serializers
from ..models import Inventario
from apps_sirae.ingredientes.models import Ingrediente


class InventarioSerializer(serializers.ModelSerializer):
    ingrediente_nombre = serializers.SerializerMethodField(read_only=True)
    categoria_nombre = serializers.SerializerMethodField(read_only=True)
    marca = serializers.SerializerMethodField(read_only=True)
    unidad_medida_nombre = serializers.SerializerMethodField(read_only=True)
    sede_nombre = serializers.CharField(source='id_sede.nombre_sede', read_only=True)

    class Meta:
        model = Inventario
        fields = [
            'id_inventario',
            'id_sede',
            'sede_nombre',
            'id_ingrediente',
            'ingrediente_nombre',
            'categoria_nombre',
            'marca',
            'unidad_medida_nombre',
            'cantidad_actual',
            'stock_minimo',
            'id_unidad_medida',
        ]

    def _get_ingrediente(self, obj):
        if not hasattr(obj, '_cached_ingrediente'):
            obj._cached_ingrediente = Ingrediente.objects.filter(pk=obj.id_ingrediente).first()
        return obj._cached_ingrediente

    def get_ingrediente_nombre(self, obj):
        try:
            ing = self._get_ingrediente(obj)
            return ing.nombre_ingrediente if ing else None
        except Exception:
            return None

    def get_categoria_nombre(self, obj):
        try:
            ing = self._get_ingrediente(obj)
            if ing and ing.id_categoria_inventario:
                return ing.id_categoria_inventario.nombre_categoria
            return None
        except Exception:
            return None

    def get_marca(self, obj):
        try:
            ing = self._get_ingrediente(obj)
            return ing.marca_ingrediente if ing else None
        except Exception:
            return None

    def get_unidad_medida_nombre(self, obj):
        try:
            ing = self._get_ingrediente(obj)
            if ing and ing.id_unidad_medida:
                return ing.id_unidad_medida.nombre
            return None
        except Exception:
            return None
