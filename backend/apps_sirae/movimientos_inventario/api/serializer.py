from rest_framework import serializers
from apps_sirae.movimientos_inventario.models import MovimientoInventario

class MovimientoInventarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovimientoInventario
        fields = '__all__'
        read_only_fields = ('fecha', 'id_usuario_manipuladora')

    def validate(self, data):
        ingrediente = data.get('id_ingrediente')
        tipo = data.get('tipo_movimiento')
        cantidad = data.get('cantidad')

        # Se obtiene el stock del ingrediente
        stock_actual = getattr(ingrediente, 'stock', getattr(ingrediente, 'cantidad', 0))

        if tipo and tipo.upper() == 'SALIDA' and stock_actual < cantidad:
            raise serializers.ValidationError({
                "cantidad": f"Stock insuficiente. Stock disponible: {stock_actual}, solicitado: {cantidad}"
            })
        return data