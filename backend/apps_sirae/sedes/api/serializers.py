from rest_framework import serializers
from ..models import Sede


class SedeSerializer(serializers.ModelSerializer):
  # Campo opcional para ver el nombre de la institución relacionada de forma legible
  institucion_nombre = serializers.ReadOnlyField(
      source='id_institucion.nombre_institucion'
  )

  class Meta:
    model = Sede
    fields = '__all__'