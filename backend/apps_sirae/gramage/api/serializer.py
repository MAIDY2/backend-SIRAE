from rest_framework import serializers
from ..models import Gramage

class GramageSerializer(serializers.ModelSerializer):

    class Meta:
        model = Gramage
        fields = [
            'id_gramage',
            'id_ingrediente',
            'id_grado',
            'id_unidad_medida',
            'cantidad_gramage',
            'descripcion'
        ]