from rest_framework import serializers
from apps_sirae.usuario_turno.models import UsuarioTurno

class UsuarioTurnoSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsuarioTurno
        fields = '__all__'
