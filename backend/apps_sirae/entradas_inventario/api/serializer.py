from rest_framework import serializers

from apps_sirae.entradas_inventario.models import EntradaInventario


class EntradaInventarioSerializer(serializers.ModelSerializer):

    class Meta:
        model = EntradaInventario
        fields = '__all__'
        read_only_fields = ('fecha', 'id_usuario')