from rest_framework import serializers

from ..models import AsistenciaDiaria


class AsistenciaDiariaSerializer(serializers.ModelSerializer):
    class Meta:
        model = AsistenciaDiaria
        fields = '__all__'