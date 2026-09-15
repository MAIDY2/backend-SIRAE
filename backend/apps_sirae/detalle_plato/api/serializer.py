from rest_framework import serializers
from apps_sirae.detalle_plato.models import DetallePlato


class DetallePlatoSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetallePlato
        fields = [
            'id_detalle_plato',
            'id_menu',
            'id_plato',
            'porcion_por_nino',
            'total_a_preparar',
            'unidad_total',
            'estado_preparacion',
        ]