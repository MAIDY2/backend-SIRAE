from rest_framework import serializers
from ..models import Plato
from apps_sirae.receta_componente.api.serializer import RecetaComponenteSerializer
from apps_sirae.pasospreparacion.models import pasospreparacion
from apps_sirae.pasospreparacion.serializers import PasosPreparacionSerializer


class PlatoSerializer(serializers.ModelSerializer):
    receta_componentes = RecetaComponenteSerializer(many=True, read_only=True)
    pasos_preparacion = serializers.SerializerMethodField()

    class Meta:
        model = Plato
        fields = [
            'id_plato',
            'id_seccion',
            'nombre_plato',
            'componente',
            'receta_componentes',
            'pasos_preparacion',
        ]

    def get_pasos_preparacion(self, obj):
        pasos = pasospreparacion.objects.filter(id_plato=obj.id_plato)
        return PasosPreparacionSerializer(pasos, many=True).data