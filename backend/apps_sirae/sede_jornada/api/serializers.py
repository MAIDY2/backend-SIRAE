from rest_framework import serializers
from ..models import SedeJornada


class SedeJornadaSerializer(serializers.ModelSerializer):

  class Meta:
    model = SedeJornada
    fields = '__all__'