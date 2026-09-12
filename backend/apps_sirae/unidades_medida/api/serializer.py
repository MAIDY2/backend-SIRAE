from rest_framework import serializers
from apps_sirae.unidades_medida.models import UnidadMedida


class UnidadMedidaSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnidadMedida
        fields = [
            'id_unidad_medida',
            'nombre',
            'abreviatura',
        ]