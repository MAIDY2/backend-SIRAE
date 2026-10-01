from rest_framework import serializers

from ..models import RecetaComponente


class RecetaComponenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecetaComponente
        fields = [
            'id_receta_componente',
            'id_plato',
            'id_ingrediente',
            'cantidad'
        ]
