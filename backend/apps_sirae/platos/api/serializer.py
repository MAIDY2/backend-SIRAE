from rest_framework import serializers
from apps_sirae.platos.models import Plato


class PlatoSerializer(serializers.ModelSerializer):
    nombre_seccion = serializers.CharField(
        source='id_seccion_menu.nombre',
        read_only=True
    )

    class Meta:
        model = Plato
        fields = [
            'id_plato',
            'nombre',
            'descripcion',
            'precio',
            'id_seccion_menu',
            'nombre_seccion',
            'imagen',
            'activo',
        ]