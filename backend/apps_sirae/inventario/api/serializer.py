from rest_framework import serializers
from ..models import Inventario

class InventarioSerializer(serializers.ModelSerializer):

    class Meta:
        model = Inventario
        fields = [
            'id_inventario',
            'id_ingrediente',
            'cantidad_actual',
            'stock_minimo',
            'id_unidad_medida',
        ]