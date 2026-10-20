from rest_framework import serializers
from apps_sirae.ingredientes.models import Ingrediente


class IngredienteSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='id_categoria_inventario.nombre_categoria', read_only=True)
    unidad_nombre = serializers.CharField(source='id_unidad_medida.nombre', read_only=True)
    unidad_abreviatura = serializers.CharField(source='id_unidad_medida.abreviatura', read_only=True)
    tipo_mercado_nombre = serializers.CharField(source='id_tipo_mercado.nombre_tipo', read_only=True)

    class Meta:
        model = Ingrediente
        fields = '__all__'

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

