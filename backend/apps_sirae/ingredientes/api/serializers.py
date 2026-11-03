from rest_framework import serializers
from apps_sirae.ingredientes.models import Ingrediente


class IngredienteSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='id_categoria_inventario.nombre_categoria', read_only=True)
    unidad_nombre = serializers.CharField(source='id_unidad_medida.nombre', read_only=True)
    unidad_abreviatura = serializers.CharField(source='id_unidad_medida.abreviatura', read_only=True)
    tipo_mercado_nombre = serializers.CharField(source='id_tipo_mercado.nombre_tipo', read_only=True)
    tiene_movimientos = serializers.SerializerMethodField()

    class Meta:
        model = Ingrediente
        fields = '__all__'

    def get_tiene_movimientos(self, obj):
        if not obj or not obj.pk:
            return False
        from apps_sirae.facturas_compra.models import DetalleFacturaCompra
        from apps_sirae.entregas.models import Entrega
        from apps_sirae.inventario.models import Inventario

        return (
            DetalleFacturaCompra.objects.filter(id_ingrediente=obj).exists() or
            Entrega.objects.filter(id_ingrediente=obj.id_ingrediente).exists() or
            Inventario.objects.filter(id_ingrediente=obj.id_ingrediente, cantidad_actual__gt=0).exists()
        )

    def validate(self, attrs):
        if self.instance and 'id_unidad_medida' in attrs:
            nueva_unidad = attrs.get('id_unidad_medida')
            if nueva_unidad and self.instance.id_unidad_medida and nueva_unidad != self.instance.id_unidad_medida:
                from apps_sirae.facturas_compra.models import DetalleFacturaCompra
                from apps_sirae.entregas.models import Entrega
                from apps_sirae.inventario.models import Inventario

                tiene_movimientos = (
                    DetalleFacturaCompra.objects.filter(id_ingrediente=self.instance).exists() or
                    Entrega.objects.filter(id_ingrediente=self.instance.id_ingrediente).exists() or
                    Inventario.objects.filter(id_ingrediente=self.instance.id_ingrediente, cantidad_actual__gt=0).exists()
                )
                if tiene_movimientos:
                    raise serializers.ValidationError({
                        'id_unidad_medida': 'No se puede modificar la unidad de medida porque este ingrediente ya registra compras, entregas o existencias en inventario. Modificar la unidad corrompería el historial de cantidades.'
                    })
        return super().validate(attrs)

    def validate_nombre_ingrediente(self, value):
        if value:
            nombre_limpio = value.strip()
            # Validación insensible a mayúsculas/minúsculas para no duplicar 'Leche', 'leche', etc.
            query = Ingrediente.objects.filter(nombre_ingrediente__iexact=nombre_limpio)
            if self.instance:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise serializers.ValidationError(
                    f"El ingrediente '{nombre_limpio}' ya está registrado. No puedes volver a registrarlo."
                )
            return nombre_limpio
        return value

