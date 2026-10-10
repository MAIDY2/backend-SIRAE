from rest_framework import serializers
from apps_sirae.tipos_mercado.models import TipoMercado

class TipoMercadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoMercado
        fields = ['id_tipo_mercado',
                'nombre_tipo'
                ]