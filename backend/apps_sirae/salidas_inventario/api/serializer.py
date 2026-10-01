from rest_framework import serializers

from apps_sirae.salidas_inventario.models import SalidaInventario


class SalidaInventarioSerializer(serializers.ModelSerializer):

    class Meta:
        model = SalidaInventario
        fields = '__all__'
        read_only_fields = ('fecha', 'id_usuario')