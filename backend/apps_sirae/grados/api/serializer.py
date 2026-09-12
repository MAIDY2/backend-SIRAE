from rest_framework import serializers
from ..models import Grados

class GradosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grados
        fields = [
            'id_grado',
            'nombre_grado',
        ]