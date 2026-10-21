from rest_framework import serializers
from ..models import SedeJornada


class SedeJornadaSerializer(serializers.ModelSerializer):
  nombre_sede = serializers.CharField(source='id_sede.nombre_sede', read_only=True)
  nombre_jornada = serializers.CharField(source='id_jornada.nombre_jornada', read_only=True)

  class Meta:
    model = SedeJornada
    fields = '__all__'