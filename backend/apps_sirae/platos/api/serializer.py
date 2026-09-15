from rest_framework import serializers
from apps_sirae.platos.models import Plato

class PlatoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plato
        fields = [
            'id_plato',
            'id_seccion',
            'nombre_plato',
            'componente',
        ]