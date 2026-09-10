from rest_framework import serializers
from apps_sirae.secciones_menu.models import SeccionMenu


class SeccionMenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeccionMenu
        fields = [
            'id_seccion_menu',
            'nombre',
            'descripcion',
            'activo',
        ]