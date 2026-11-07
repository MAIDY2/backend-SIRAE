from rest_framework import serializers

from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.tipos_mercado.models import TipoMercado
from apps_sirae.sedes.models import Sede

from apps_sirae.entregas.models import Entrega


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

    def validate(self, attrs):
        id_ingrediente = attrs.get('id_ingrediente') or getattr(self.instance, 'id_ingrediente', None)
        if id_ingrediente:
            try:
                ing = Ingrediente.objects.select_related('id_unidad_medida', 'id_tipo_mercado').get(pk=id_ingrediente)
                # Auto-completar o fijar la unidad desde el ingrediente maestro
                if ing.id_unidad_medida:
                    attrs['unidad'] = ing.id_unidad_medida.abreviatura or ing.id_unidad_medida.nombre

                # Auto-completar id_tipo_mercado desde el ingrediente
                if ing.id_tipo_mercado_id:
                    attrs['id_tipo_mercado'] = ing.id_tipo_mercado_id
                elif ing.tipo_conservacion and not attrs.get('id_tipo_mercado'):
                    es_per = 'no' not in ing.tipo_conservacion.lower()
                    tm = TipoMercado.objects.filter(nombre_tipo__icontains='pereced').exclude(nombre_tipo__icontains='no').first() if es_per else TipoMercado.objects.filter(nombre_tipo__icontains='no').first()
                    if tm:
                        attrs['id_tipo_mercado'] = tm.id_tipo_mercado
            except Ingrediente.DoesNotExist:
                pass
        id_sede = attrs.get('id_sede') or getattr(self.instance, 'id_sede', None)
        id_inst = attrs.get('id_institucion') or getattr(self.instance, 'id_institucion', None)
        if id_sede and id_inst:
            inst_id_val = id_inst.pk if hasattr(id_inst, 'pk') else id_inst
            sede_inst_val = getattr(id_sede, 'id_institucion_id', None)
            if sede_inst_val is None and hasattr(id_sede, 'pk'):
                sede_inst_val = Sede.objects.filter(pk=id_sede.pk).values_list('id_institucion_id', flat=True).first()
            if sede_inst_val and sede_inst_val != inst_id_val:
                raise serializers.ValidationError(
                    {'id_sede': 'La sede seleccionada no pertenece a la institución receptora.'}
                )

        return super().validate(attrs)

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