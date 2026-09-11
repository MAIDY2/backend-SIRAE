from rest_framework import serializers

from ..models import Menu


class MenuSerializer(serializers.ModelSerializer):

    class Meta:
        model = Menu
        fields = [
            "id_menu",
            "id_jornada",
            "fecha",
            "ninos_presentes",
            "estado",
            "informacion_nutricional",
            "id_contrato",
        ]
