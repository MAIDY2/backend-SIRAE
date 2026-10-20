from rest_framework import serializers
from ..models import Inventario
from apps_sirae.ingredientes.models import Ingrediente


class InventarioSerializer(serializers.ModelSerializer):
    ingrediente_nombre = serializers.SerializerMethodField(read_only=True)
    sede_nombre = serializers.CharField(source='id_sede.nombre_sede', read_only=True)

    class Meta:
        model = Inventario
        fields = [
            'id_inventario',
            'id_sede',
            'sede_nombre',
            'id_ingrediente',
            'ingrediente_nombre',
            'cantidad_actual',
            'stock_minimo',
            'id_unidad_medida',
        ]

    def get_ingrediente_nombre(self, obj):
        try:
            ing = Ingrediente.objects.filter(pk=obj.id_ingrediente).first()
            return ing.nombre_ingrediente if ing else None
        except Exception:
            return None