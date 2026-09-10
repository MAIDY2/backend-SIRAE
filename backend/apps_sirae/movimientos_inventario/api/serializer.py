from rest_framework import serializers

from ..models import MovimientoInventario


class MovimientoInventarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovimientoInventario
        fields = '__all__'