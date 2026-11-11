from rest_framework import serializers

from apps_sirae.reportes.models import PlanillaGenerada, PlantillaOficial, PlantillaVersion


class PlantillaVersionSerializer(serializers.ModelSerializer):
    es_inmutable = serializers.SerializerMethodField()
    creado_por_nombre = serializers.SerializerMethodField()
    publicado_por_nombre = serializers.SerializerMethodField()
    total_planillas_generadas = serializers.SerializerMethodField()

    class Meta:
        model = PlantillaVersion
        fields = [
            'id_version',
            'id_plantilla',
            'numero_version',
            'estado',
            'esquema',
            'notas_version',
            'creado_por_nombre',
            'publicado_por_nombre',
            'fecha_creacion',
            'fecha_publicacion',
            'fecha_actualizacion',
            'es_inmutable',
            'total_planillas_generadas',
        ]

    def get_es_inmutable(self, obj):
        return obj.es_inmutable()

    def get_creado_por_nombre(self, obj):
        return obj.creado_por.nombre_completo if obj.creado_por else ''

    def get_publicado_por_nombre(self, obj):
        return obj.publicado_por.nombre_completo if obj.publicado_por else ''

    def get_total_planillas_generadas(self, obj):
        return obj.planillas_generadas.count()


class PlantillaOficialSerializer(serializers.ModelSerializer):
    versiones = PlantillaVersionSerializer(many=True, read_only=True)
    version_publicada = serializers.SerializerMethodField()
    version_borrador = serializers.SerializerMethodField()
    categoria_proceso_display = serializers.CharField(source='get_categoria_proceso_display', read_only=True)

    class Meta:
        model = PlantillaOficial
        fields = [
            'id_plantilla',
            'codigo',
            'nombre',
            'descripcion',
            'categoria_proceso',
            'categoria_proceso_display',
            'finalidad',
            'roles_autorizados',
            'activa',
            'fecha_creacion',
            'fecha_actualizacion',
            'version_publicada',
            'version_borrador',
            'versiones',
        ]

    def get_version_publicada(self, obj):
        v = obj.versiones.filter(estado='PUBLICADA').order_by('-numero_version').first()
        return PlantillaVersionSerializer(v).data if v else None

    def get_version_borrador(self, obj):
        v = obj.versiones.filter(estado='BORRADOR').order_by('-numero_version').first()
        return PlantillaVersionSerializer(v).data if v else None


class PlanillaGeneradaListSerializer(serializers.ModelSerializer):
    institucion_nombre = serializers.CharField(source='id_institucion.nombre_institucion', read_only=True)
    sede_nombre = serializers.SerializerMethodField()
    contrato_numero = serializers.SerializerMethodField()
    jornada_nombre = serializers.SerializerMethodField()
    plantilla_id = serializers.IntegerField(source='id_plantilla_version.id_plantilla_id', read_only=True)
    plantilla_codigo = serializers.CharField(source='id_plantilla_version.id_plantilla.codigo', read_only=True)
    plantilla_nombre = serializers.CharField(source='id_plantilla_version.id_plantilla.nombre', read_only=True)
    version_numero = serializers.IntegerField(source='id_plantilla_version.numero_version', read_only=True)
    total_pendientes = serializers.SerializerMethodField()

    class Meta:
        model = PlanillaGenerada
        fields = [
            'id_planilla',
            'codigo_documento',
            'nombre_documento',
            'categoria_proceso',
            'estado',
            'periodo',
            'fecha_inicio',
            'fecha_fin',
            'id_institucion',
            'institucion_nombre',
            'id_sede',
            'sede_nombre',
            'id_contrato',
            'contrato_numero',
            'id_jornada',
            'jornada_nombre',
            'id_plantilla_version',
            'plantilla_id',
            'plantilla_codigo',
            'plantilla_nombre',
            'version_numero',
            'evento_origen',
            'responsable_nombre',
            'fecha_generacion',
            'fecha_actualizacion',
            'fecha_revision',
            'total_pendientes',
            'observaciones',
        ]

    def get_sede_nombre(self, obj):
        return obj.id_sede.nombre_sede if obj.id_sede else 'Consolidado institucional'

    def get_contrato_numero(self, obj):
        return obj.id_contrato.numero_cor if obj.id_contrato else ''

    def get_jornada_nombre(self, obj):
        return obj.id_jornada.nombre_jornada if obj.id_jornada else 'Todas las jornadas'

    def get_total_pendientes(self, obj):
        return len(obj.campos_pendientes or [])


class PlanillaGeneradaDetailSerializer(PlanillaGeneradaListSerializer):
    revisado_por_nombre = serializers.SerializerMethodField()

    class Meta(PlanillaGeneradaListSerializer.Meta):
        fields = PlanillaGeneradaListSerializer.Meta.fields + [
            'contenido_snapshot',
            'valores_manuales',
            'campos_pendientes',
            'registros_origen',
            'revisado_por_nombre',
        ]

    def get_revisado_por_nombre(self, obj):
        return obj.revisado_por.nombre_completo if obj.revisado_por else ''

