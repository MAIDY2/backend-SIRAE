from rest_framework import serializers

from ..models import Contrato


class ContratoSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Contrato
        fields = [
            "id_plato",
            "numero_paso",
            "descripcion_paso",
        ]
        
