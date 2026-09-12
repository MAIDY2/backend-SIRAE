from rest_framework import serializers

from .models import pasospreparacion


class PasosPreparacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = pasospreparacion
        fields = [
            'id_plato',
            'numero_paso',
            'descripcion',
        ]
