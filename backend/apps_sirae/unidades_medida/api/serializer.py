from rest_framework import serializers
from ..models import UnidadMedida


class UnidadMedidaSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnidadMedida
<<<<<<< HEAD
        fields = [
            'id_unidad_medida',
            'nombre',
            'abreviatura',
        ]
=======
        fields = ['id_unidad_medida', 'nombre_unidad', 'abreviatura']
>>>>>>> f7be33e5f87ff6d750f1ab487464488a2fc533ad
