from rest_framework import serializers
from ..models import SeccionMenu


class SeccionMenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeccionMenu
        fields = [
            'id_seccion',
            'id_jornada',
            'nombre_seccion',
        ]