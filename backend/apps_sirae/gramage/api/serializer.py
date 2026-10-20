from rest_framework import serializers
from ..models import Gramage

class GramageSerializer(serializers.ModelSerializer):
    id_gramage = serializers.IntegerField(source='id_gramaje', read_only=True)
    cantidad_gramage = serializers.DecimalField(
        max_digits=8, decimal_places=3, source='cantidad_gramaje', required=False
    )

    class Meta:
        model = Gramage
        fields = [
            'id_gramaje',
            'id_gramage',
            'id_ingrediente',
            'id_grado',
            'id_unidad_medida',
            'cantidad_gramaje',
            'cantidad_gramage',
            'descripcion'
        ]