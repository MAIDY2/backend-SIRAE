from rest_framework import serializers

from ..models import ContratoSeccionMenu


class ContratoSeccionMenuSerializer(serializers.ModelSerializer):

    class Meta:
        model = ContratoSeccionMenu
        fields = '__all__'