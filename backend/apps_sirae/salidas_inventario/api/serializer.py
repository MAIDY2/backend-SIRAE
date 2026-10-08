from rest_framework import serializers
from apps_sirae.salidas_inventario.models import SalidaInventario
from apps_sirae.inventario.models import Inventario  # Importamos Inventario


class SalidaInventarioSerializer(serializers.ModelSerializer):

    class Meta:
        model = SalidaInventario
        fields = '__all__'
        read_only_fields = ('fecha', 'id_usuario')

    def validate(self, data):
        # 1. Obtener el ingrediente y la cantidad ingresados desde el frontend
        id_ing = data.get('id_ingrediente')
        cantidad = data.get('cantidad')

        if cantidad is None or cantidad <= 0:
            raise serializers.ValidationError({"cantidad": "La cantidad debe ser mayor a 0."})

        # 2. Consultar el stock actual en la tabla 'inventario'
        try:
            # Si id_ingrediente es ForeignKey en SalidaInventario, id_ing ya es la instancia del Ingrediente
            inventario = Inventario.objects.get(id_ingrediente=id_ing)

            if inventario.cantidad_actual < cantidad:
                raise serializers.ValidationError({
                    "cantidad": f"Stock insuficiente. Disponible: {inventario.cantidad_actual}, intentas retirar: {cantidad}"
                })
        except Inventario.DoesNotExist:
            raise serializers.ValidationError({
                "id_ingrediente": "Este ingrediente aún no tiene un registro activo en el inventario."
            })

        return data