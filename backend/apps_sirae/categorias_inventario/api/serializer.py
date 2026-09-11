from rest_framework import serializers

from ..models import CategoriaInventario


class CategoriaInventarioSerializer(serializers.ModelSerializer):

    class Meta:
        model = CategoriaInventario
        fields = [
            "id_categoria_inventario",
            "nombre_categoria",
        ]
