from rest_framework import serializers

from .models import pasospreparacion


class PasosPreparacionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='pk', read_only=True)
    descripcion_paso = serializers.CharField(source='descripcion', read_only=True)

    class Meta:
        model = pasospreparacion
        fields = [
            'id',
            'id_plato',
            'numero_paso',
            'descripcion',
            'descripcion_paso',
        ]

    def to_internal_value(self, data):
        mutable = data.copy() if hasattr(data, 'copy') else dict(data)
        if not mutable.get('descripcion') and mutable.get('descripcion_paso'):
            mutable['descripcion'] = str(mutable['descripcion_paso'])[:100]
        if mutable.get('numero_paso') is not None:
            mutable['numero_paso'] = str(mutable['numero_paso'])
        return super().to_internal_value(mutable)
