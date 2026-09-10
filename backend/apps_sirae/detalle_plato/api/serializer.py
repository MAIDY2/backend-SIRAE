from rest_framework import serializers
from apps_sirae.detalle_plato.models import DetallePlato


class DetallePlatoSerializer(serializers.ModelSerializer):
    nombre_plato = serializers.CharField(
        source='id_plato.nombre',
        read_only=True
    )
    nombre_unidad = serializers.CharField(
        source='id_unidad_medida.nombre',
        read_only=True
    )
    abreviatura_unidad = serializers.CharField(
        source='id_unidad_medida.abreviatura',
        read_only=True
    )

    class Meta:
        model = DetallePlato
        fields = [
            'id_detalle_plato',
            'id_plato',
            'nombre_plato',
            'ingrediente',
            'cantidad',
            'id_unidad_medida',
            'nombre_unidad',
            'abreviatura_unidad',
            'observaciones',
        ]