from rest_framework import serializers
from apps_sirae.roles.models import Rol


class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = ['id_rol', 'nombre', 'descripcion']