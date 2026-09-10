from rest_framework import serializers
from apps_sirae.roles.models import Rol


class RolSerializer(serializers.ModelSerializer):

    nombre_display = serializers.CharField(
        source='get_nombre_display',
        read_only=True
    )

    class Meta:
        model  = Rol
        fields = ['id_rol', 'nombre', 'nombre_display', 'descripcion']
