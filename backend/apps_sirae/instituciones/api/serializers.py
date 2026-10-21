from rest_framework import serializers

# Cambia esto: from .models import Institucion
from ..models import Institucion


class InstitucionSerializer(serializers.ModelSerializer):

  class Meta:
    model = Institucion
    fields = '__all__'