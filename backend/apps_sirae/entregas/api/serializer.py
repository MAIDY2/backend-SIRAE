from rest_framework import serializers

from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.tipos_mercado.models import TipoMercado

from ..models import Entrega


class EntregaSerializer(serializers.ModelSerializer):
    ingrediente_nombre = serializers.SerializerMethodField()
    tipo_mercado_nombre = serializers.SerializerMethodField()
    institucion_nombre = serializers.CharField(source='id_institucion.nombre_institucion', read_only=True)
    sede_nombre = serializers.CharField(source='id_sede.nombre_sede', read_only=True)
    usuario_receptor_nombre = serializers.CharField(source='id_usuario_receptor.nombre_completo', read_only=True)

    class Meta:
        model = Entrega
        fields = [
            'id_entrega',
            'id_institucion',
            'institucion_nombre',
            'id_sede',
            'sede_nombre',
            'id_ingrediente',
            'ingrediente_nombre',
            'id_usuario_supervisor',
            'id_tipo_mercado',
            'tipo_mercado_nombre',
            'fecha_entrega',
            'fecha_vencimiento',
            'cantidad',
            'estado',
            'cantidad_recibida',
            'cantidad_rechazada',
            'motivo_rechazo',
            'id_usuario_receptor',
            'usuario_receptor_nombre',
            'fecha_recepcion',
            'observaciones',
            'frecuencia',
            'unidad',
        ]
        read_only_fields = [
            'id_entrega',
            'id_usuario_supervisor',
            'id_usuario_receptor',
            'fecha_recepcion',
        ]

    def get_ingrediente_nombre(self, entrega):
        return Ingrediente.objects.filter(
            pk=entrega.id_ingrediente
        ).values_list('nombre_ingrediente', flat=True).first()

    def get_tipo_mercado_nombre(self, entrega):
        return TipoMercado.objects.filter(
            pk=entrega.id_tipo_mercado
        ).values_list('nombre_tipo', flat=True).first()