from rest_framework import serializers
from apps_sirae.turnos.models import Turno

class TurnoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Turno
        fields = '__all__'
