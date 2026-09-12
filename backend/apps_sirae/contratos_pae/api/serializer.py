from rest_framework import serializers

from ..models import Contrato


class ContratoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contrato
        fields = [
            "id_contrato",
            "numero_cor",
            "institucion",
            "zona",
            "fecha_inicio",
            "fecha_fin",
            "estado"
        ]

