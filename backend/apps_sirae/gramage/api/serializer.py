from decimal import Decimal
from rest_framework import serializers

from apps_sirae.unidades_medida.services import verificar_compatibilidad_unidades
from ..models import Gramage, HistorialGramaje


class HistorialGramajeSerializer(serializers.ModelSerializer):
    usuario_modificacion_nombre = serializers.SerializerMethodField()

    class Meta:
        model = HistorialGramaje
        fields = [
            'id_historial_gramaje',
            'id_gramaje',
            'tipo_evento',
            'cantidad_anterior',
            'cantidad_nueva',
            'unidad_anterior',
            'unidad_nueva',
            'estado_anterior',
            'estado_nuevo',
            'contexto_anterior',
            'contexto_nuevo',
            'observaciones',
            'id_usuario_modificacion',
            'usuario_modificacion_nombre',
            'fecha_cambio',
        ]

    def get_usuario_modificacion_nombre(self, obj):
        if obj.id_usuario_modificacion:
            return f"{obj.id_usuario_modificacion.nombre} {obj.id_usuario_modificacion.apellido}".strip()
        return None


class GramageSerializer(serializers.ModelSerializer):
    id_gramage = serializers.IntegerField(source='id_gramaje', read_only=True)
    cantidad_gramage = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        source='cantidad_gramaje',
        read_only=True,
    )
    nombre_ingrediente = serializers.CharField(
        source='id_ingrediente.nombre_ingrediente',
        read_only=True,
        default=None,
    )
    id_categoria_inventario = serializers.IntegerField(
        source='id_ingrediente.id_categoria_inventario_id',
        read_only=True,
        default=None,
    )
    nombre_categoria = serializers.SerializerMethodField()
    tipo_conservacion = serializers.CharField(
        source='id_ingrediente.tipo_conservacion',
        read_only=True,
        default='no_perecedero',
    )
    tipo_alimento_display = serializers.SerializerMethodField()
    nombre_grado = serializers.CharField(
        source='id_grado.nombre_grado',
        read_only=True,
        default=None,
    )
    id_grupo_gramaje = serializers.IntegerField(
        source='id_grado.id_grupo_gramaje_id',
        read_only=True,
        default=None,
    )
    nombre_grupo_gramaje = serializers.SerializerMethodField()
    nivel_educativo = serializers.CharField(
        source='id_grado.nivel_educativo',
        read_only=True,
        default=None,
    )
    nombre_unidad_medida = serializers.CharField(
        source='id_unidad_medida.nombre',
        read_only=True,
        default=None,
    )
    abreviatura_unidad_medida = serializers.CharField(
        source='id_unidad_medida.abreviatura',
        read_only=True,
        default=None,
    )
    tipo_magnitud_unidad = serializers.CharField(
        source='id_unidad_medida.tipo_magnitud',
        read_only=True,
        default=None,
    )
    contexto_aplicacion_display = serializers.CharField(
        source='get_contexto_aplicacion_display',
        read_only=True,
    )
    usuario_modificacion_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Gramage
        fields = [
            'id_gramaje',
            'id_gramage',
            'id_ingrediente',
            'nombre_ingrediente',
            'id_categoria_inventario',
            'nombre_categoria',
            'tipo_conservacion',
            'tipo_alimento_display',
            'id_grado',
            'nombre_grado',
            'id_grupo_gramaje',
            'nombre_grupo_gramaje',
            'nivel_educativo',
            'id_unidad_medida',
            'nombre_unidad_medida',
            'abreviatura_unidad_medida',
            'tipo_magnitud_unidad',
            'cantidad_gramaje',
            'cantidad_gramage',
            'valor_anterior',
            'contexto_aplicacion',
            'contexto_aplicacion_display',
            'descripcion',
            'estado',
            'fecha_creacion',
            'fecha_actualizacion',
            'id_usuario_modificacion',
            'usuario_modificacion_nombre',
        ]
        read_only_fields = [
            'id_gramaje',
            'id_gramage',
            'valor_anterior',
            'fecha_creacion',
            'fecha_actualizacion',
            'id_usuario_modificacion',
        ]

    def to_internal_value(self, data):
        if isinstance(data, dict) and 'cantidad_gramage' in data and 'cantidad_gramaje' not in data:
            data = data.copy()
            data['cantidad_gramaje'] = data['cantidad_gramage']
        return super().to_internal_value(data)

    def get_nombre_categoria(self, obj):
        cat = getattr(obj.id_ingrediente, 'id_categoria_inventario', None) if obj.id_ingrediente_id else None
        return getattr(cat, 'nombre_categoria', None) if cat else None

    def get_tipo_alimento_display(self, obj):
        if not obj.id_ingrediente_id:
            return None
        return 'Perecedero' if obj.id_ingrediente.tipo_conservacion == 'perecedero' else 'No perecedero'

    def get_nombre_grupo_gramaje(self, obj):
        if obj.id_grado_id and obj.id_grado.id_grupo_gramaje_id:
            return obj.id_grado.id_grupo_gramaje.nombre
        return None

    def get_usuario_modificacion_nombre(self, obj):
        if obj.id_usuario_modificacion:
            return f"{obj.id_usuario_modificacion.nombre} {obj.id_usuario_modificacion.apellido}".strip()
        return None

    def validate(self, attrs):
        ingrediente = attrs.get(
            'id_ingrediente',
            self.instance.id_ingrediente if self.instance else None,
        )
        grado = attrs.get(
            'id_grado',
            self.instance.id_grado if self.instance else None,
        )
        unidad = attrs.get(
            'id_unidad_medida',
            self.instance.id_unidad_medida if self.instance else None,
        )
        cantidad = attrs.get(
            'cantidad_gramaje',
            self.instance.cantidad_gramaje if self.instance else None,
        )
        contexto = attrs.get(
            'contexto_aplicacion',
            self.instance.contexto_aplicacion if self.instance else 'GENERAL',
        ) or 'GENERAL'
        estado = attrs.get(
            'estado',
            self.instance.estado if self.instance else 'ACTIVO',
        ) or 'ACTIVO'

        errores = {}
        if not self.partial or 'id_ingrediente' in attrs:
            if ingrediente is None:
                errores['id_ingrediente'] = "El producto o ingrediente es obligatorio."
        if not self.partial or 'id_grado' in attrs:
            if grado is None:
                errores['id_grado'] = "El grado escolar es obligatorio."
        if not self.partial or 'id_unidad_medida' in attrs:
            if unidad is None:
                errores['id_unidad_medida'] = "La unidad de medida es obligatoria."
        if not self.partial or 'cantidad_gramaje' in attrs:
            if cantidad is None:
                errores['cantidad_gramaje'] = "La cantidad de gramaje es obligatoria."

        if errores:
            raise serializers.ValidationError(errores)

        if cantidad is not None and Decimal(str(cantidad)) <= Decimal('0'):
            raise serializers.ValidationError({
                'cantidad_gramaje': "La cantidad de gramaje debe ser mayor que cero."
            })

        if grado is not None and (self.instance is None or self.instance.id_grado_id != grado.pk):
            if getattr(grado, 'estado', 'ACTIVO') != 'ACTIVO':
                raise serializers.ValidationError({
                    'id_grado': f"El grado '{grado.nombre_grado}' se encuentra inactivo."
                })

        if unidad is not None and (self.instance is None or self.instance.id_unidad_medida_id != unidad.pk):
            if getattr(unidad, 'estado', 'ACTIVO') != 'ACTIVO':
                raise serializers.ValidationError({
                    'id_unidad_medida': f"La unidad '{unidad.nombre}' se encuentra inactiva."
                })

        # HU 3: Validar compatibilidad de unidad del gramaje vs unidad base del producto
        if ingrediente is not None and unidad is not None:
            unidad_base = getattr(ingrediente, 'id_unidad_medida', None)
            if unidad_base is not None:
                es_compatible, _, _ = verificar_compatibilidad_unidades(
                    unidad, unidad_base, ingrediente=ingrediente
                )
                if not es_compatible:
                    raise serializers.ValidationError({
                        'id_unidad_medida': (
                            f"La unidad '{unidad.nombre} ({unidad.abreviatura})' no es compatible con "
                            f"la unidad base de '{ingrediente.nombre_ingrediente}' "
                            f"('{unidad_base.nombre} ({unidad_base.abreviatura})'). "
                            "Configure una equivalencia técnica entre estas unidades antes de continuar."
                        )
                    })

        # HU 1: No duplicar configuración activa para mismo producto, grado y contexto
        if estado == 'ACTIVO' and ingrediente is not None and grado is not None:
            duplicados = Gramage.objects.filter(
                id_ingrediente=ingrediente,
                id_grado=grado,
                contexto_aplicacion=contexto,
                estado='ACTIVO',
            )
            if self.instance is not None:
                duplicados = duplicados.exclude(pk=self.instance.pk)
            if duplicados.exists():
                raise serializers.ValidationError({
                    'non_field_errors': (
                        f"Ya existe una configuración ACTIVA para '{ingrediente.nombre_ingrediente}', "
                        f"grado '{grado.nombre_grado}' y contexto '{contexto}'. "
                        "Edite la configuración existente o inactívela antes de crear otra."
                    )
                })

        return attrs