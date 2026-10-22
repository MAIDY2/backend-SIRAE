from rest_framework import serializers

from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.tipos_mercado.models import TipoMercado

from ..models import Entrega


class EntregaSerializer(serializers.ModelSerializer):
    ingrediente_nombre = serializers.SerializerMethodField()
    tipo_mercado_nombre = serializers.SerializerMethodField()
    institucion_nombre = serializers.SerializerMethodField()
    sede_nombre = serializers.SerializerMethodField()
    usuario_receptor_nombre = serializers.SerializerMethodField()

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
        if not entrega.id_ingrediente:
            return ''
        return Ingrediente.objects.filter(
            pk=entrega.id_ingrediente
        ).values_list('nombre_ingrediente', flat=True).first() or ''

    def get_tipo_mercado_nombre(self, entrega):
        if not entrega.id_tipo_mercado:
            return ''
        return TipoMercado.objects.filter(
            pk=entrega.id_tipo_mercado
        ).values_list('nombre_tipo', flat=True).first() or ''

    def get_institucion_nombre(self, entrega):
        if entrega.id_institucion:
            return getattr(entrega.id_institucion, 'nombre_institucion', '')
        if entrega.id_sede and getattr(entrega.id_sede, 'id_institucion', None):
            return getattr(entrega.id_sede.id_institucion, 'nombre_institucion', '')
        return ''

    def get_sede_nombre(self, entrega):
        if entrega.id_sede:
            return getattr(entrega.id_sede, 'nombre_sede', '')
        return ''

    def get_usuario_receptor_nombre(self, entrega):
        if entrega.id_usuario_receptor:
            return f"{entrega.id_usuario_receptor.nombre} {entrega.id_usuario_receptor.apellido}".strip()
        return None