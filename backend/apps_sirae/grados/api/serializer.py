from rest_framework import serializers
from ..models import Grados, GrupoGramaje, HistorialClasificacionGrado


class GrupoGramajeSerializer(serializers.ModelSerializer):
    nivel_educativo_display = serializers.CharField(
        source='get_nivel_educativo_display',
        read_only=True,
    )
    grados_count = serializers.SerializerMethodField()
    grados_asociados = serializers.SerializerMethodField()

    class Meta:
        model = GrupoGramaje
        fields = [
            'id_grupo_gramaje',
            'nombre',
            'nivel_educativo',
            'nivel_educativo_display',
            'descripcion',
            'estado',
            'fecha_actualizacion',
            'grados_count',
            'grados_asociados',
        ]
        read_only_fields = ['id_grupo_gramaje', 'fecha_actualizacion']

    def get_grados_count(self, obj):
        return obj.grados.count()

    def get_grados_asociados(self, obj):
        return [
            {
                'id_grado': g.id_grado,
                'nombre_grado': g.nombre_grado,
                'estado': g.estado,
            }
            for g in obj.grados.all().order_by('id_grado')
        ]

    def validate_nombre(self, value):
        nombre = (value or '').strip()
        if not nombre:
            raise serializers.ValidationError("El nombre del grupo de gramaje es obligatorio.")
        qs = GrupoGramaje.objects.filter(nombre__iexact=nombre)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un grupo de gramaje con este nombre.")
        return nombre


class HistorialClasificacionGradoSerializer(serializers.ModelSerializer):
    nombre_grado = serializers.CharField(source='id_grado.nombre_grado', read_only=True)
    usuario_modificacion_nombre = serializers.SerializerMethodField()

    class Meta:
        model = HistorialClasificacionGrado
        fields = [
            'id_historial_clasificacion',
            'id_grado',
            'nombre_grado',
            'grupo_anterior',
            'grupo_nuevo',
            'nombre_grupo_anterior',
            'nombre_grupo_nuevo',
            'nivel_anterior',
            'nivel_nuevo',
            'motivo',
            'id_usuario_modificacion',
            'usuario_modificacion_nombre',
            'fecha_cambio',
        ]

    def get_usuario_modificacion_nombre(self, obj):
        if obj.id_usuario_modificacion:
            return f"{obj.id_usuario_modificacion.nombre} {obj.id_usuario_modificacion.apellido}".strip()
        return None


class GradosSerializer(serializers.ModelSerializer):
    nombre_grupo_gramaje = serializers.CharField(
        source='id_grupo_gramaje.nombre',
        read_only=True,
        default=None,
    )
    grupo_nivel_educativo = serializers.CharField(
        source='id_grupo_gramaje.nivel_educativo',
        read_only=True,
        default=None,
    )
    nivel_educativo_display = serializers.CharField(
        source='get_nivel_educativo_display',
        read_only=True,
    )
    tiene_historial = serializers.SerializerMethodField()
    motivo_cambio = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        default='',
    )

    class Meta:
        model = Grados
        fields = [
            'id_grado',
            'nombre_grado',
            'id_grupo_gramaje',
            'nombre_grupo_gramaje',
            'grupo_nivel_educativo',
            'nivel_educativo',
            'nivel_educativo_display',
            'estado',
            'fecha_actualizacion',
            'tiene_historial',
            'motivo_cambio',
        ]
        read_only_fields = ['id_grado', 'fecha_actualizacion']

    def get_tiene_historial(self, obj):
        return (
            obj.gramajes.exists()
            or obj.asistencias.exists()
            or obj.historial_clasificacion.exists()
        )

    def validate_nombre_grado(self, value):
        nombre = (value or '').strip()
        if not nombre:
            raise serializers.ValidationError("El nombre del grado es obligatorio.")
        qs = Grados.objects.filter(nombre_grado__iexact=nombre)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un grado registrado con ese nombre.")
        return nombre

    def validate(self, attrs):
        grupos_multiples = self.initial_data.get('grupos_ids') if isinstance(self.initial_data, dict) else None
        if isinstance(grupos_multiples, list) and len(grupos_multiples) > 1:
            raise serializers.ValidationError({
                'id_grupo_gramaje': "Un grado no puede quedar asociado a múltiples grupos dentro de la misma configuración."
            })

        grupo = attrs.get(
            'id_grupo_gramaje',
            self.instance.id_grupo_gramaje if self.instance else None,
        )

        if self.instance is None and grupo is None:
            raise serializers.ValidationError({
                'id_grupo_gramaje': "Cada grado debe estar asociado a su grupo de aplicación de gramajes."
            })

        if not self.partial and self.instance is not None and 'id_grupo_gramaje' in attrs and grupo is None:
            raise serializers.ValidationError({
                'id_grupo_gramaje': "Cada grado debe mantener un grupo de aplicación de gramajes asignado."
            })

        if grupo is not None:
            cambio_grupo = self.instance is None or self.instance.id_grupo_gramaje_id != grupo.pk
            if cambio_grupo and grupo.estado != 'ACTIVO':
                raise serializers.ValidationError({
                    'id_grupo_gramaje': f"El grupo '{grupo.nombre}' se encuentra inactivo y no admite nuevas asignaciones."
                })

            nivel_explicito = isinstance(self.initial_data, dict) and 'nivel_educativo' in self.initial_data
            if nivel_explicito:
                nivel = attrs.get('nivel_educativo', self.instance.nivel_educativo if self.instance else 'PRIMARIA')
                if (
                    grupo.nivel_educativo != 'OTRO'
                    and nivel != 'OTRO'
                    and nivel != grupo.nivel_educativo
                ):
                    raise serializers.ValidationError({
                        'nivel_educativo': (
                            f"Clasificación incompatible: el nivel educativo '{nivel}' no corresponde al "
                            f"grupo '{grupo.nombre}' (nivel '{grupo.nivel_educativo}'). "
                            "Un grado no puede asociarse a grupos de niveles incompatibles."
                        )
                    })
            elif cambio_grupo:
                attrs['nivel_educativo'] = grupo.nivel_educativo

        return attrs

    def create(self, validated_data):
        validated_data.pop('motivo_cambio', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('motivo_cambio', None)
        return super().update(instance, validated_data)