from rest_framework import serializers
from ..models import Plato


class PlatoSerializer(serializers.ModelSerializer):
    imagen = serializers.SerializerMethodField()

    class Meta:
        model = Plato
        fields = [
            'id_plato',
            'id_seccion',
            'nombre_plato',
            'componente',
            'imagen',
        ]

    def get_imagen(self, obj):
        return obj.imagen.url if obj.imagen else None