from decimal import Decimal
from rest_framework import serializers

from ..models import RecetaComponente


class RecetaComponenteSerializer(serializers.ModelSerializer):
    nombre_ingrediente = serializers.ReadOnlyField(
        source='id_ingrediente.nombre_ingrediente'
    )
    cantidad = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        default=Decimal('1.00'),
    )

    class Meta:
        model = RecetaComponente
        fields = [
            'id_receta_componente',
            'id_plato',
            'id_ingrediente',
            'nombre_ingrediente',
            'cantidad',
            'base_cantidad',
            'porciones_base',
        ]

    def to_internal_value(self, data):
        mutable = data.copy() if hasattr(data, 'copy') else dict(data)
        mutable.pop('id_gramaje', None)
        if mutable.get('cantidad') in (None, ''):
            mutable['cantidad'] = '1.00'
        if not mutable.get('base_cantidad'):
            mutable['base_cantidad'] = 'POR_NINO'
        return super().to_internal_value(mutable)

    def validate(self, attrs):
        cantidad = attrs.get(
            'cantidad',
            getattr(self.instance, 'cantidad', None),
        )
        if cantidad is not None and cantidad <= 0:
            raise serializers.ValidationError({
                'cantidad': 'La cantidad debe ser mayor que cero.'
            })

        base_cantidad = attrs.get(
            'base_cantidad',
            getattr(self.instance, 'base_cantidad', None),
        )
        porciones_base = attrs.get(
            'porciones_base',
            getattr(self.instance, 'porciones_base', None),
        )

        if base_cantidad not in dict(
            self.fields['base_cantidad'].choices
        ):
            raise serializers.ValidationError({
                'base_cantidad': 'Selecciona la base de la cantidad.'
            })

        if base_cantidad == 'TOTAL_PREPARACION':
            if not porciones_base or porciones_base <= 0:
                raise serializers.ValidationError({
                    'porciones_base': (
                        'Indica para cuántas porciones corresponde '
                        'la cantidad total.'
                    )
                })
        else:
            attrs['porciones_base'] = None

        return attrs
