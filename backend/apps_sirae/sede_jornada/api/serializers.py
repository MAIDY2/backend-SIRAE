from django.db import transaction
from rest_framework import serializers

from apps_sirae.grados.models import Grados
from ..models import SedeJornada, SedeJornadaGrado


class SedeJornadaSerializer(serializers.ModelSerializer):
    id_institucion = serializers.IntegerField(
        source='id_sede.id_institucion_id',
        read_only=True,
    )
    nombre_institucion = serializers.CharField(
        source='id_sede.id_institucion.nombre_institucion',
        read_only=True,
        default='',
    )
    nombre_sede = serializers.CharField(source='id_sede.nombre_sede', read_only=True)
    nombre_jornada = serializers.CharField(source='id_jornada.nombre_jornada', read_only=True)
    grados_atendidos = serializers.SerializerMethodField()
    grados_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = SedeJornada
        fields = [
            'id_sede_jornada',
            'id_institucion',
            'nombre_institucion',
            'id_sede',
            'nombre_sede',
            'id_jornada',
            'nombre_jornada',
            'cupos',
            'grados_atendidos',
            'grados_ids',
        ]

    def get_grados_atendidos(self, obj):
        relaciones = list(obj.grados_atendidos.select_related('id_grado__id_grupo_gramaje').all())
        return [
            {
                'id_sede_jornada_grado': rel.id_sede_jornada_grado,
                'id_grado': rel.id_grado_id,
                'nombre_grado': rel.id_grado.nombre_grado,
                'nivel_educativo': rel.id_grado.nivel_educativo,
                'id_grupo_gramaje': rel.id_grado.id_grupo_gramaje_id,
                'nombre_grupo_gramaje': (
                    rel.id_grado.id_grupo_gramaje.nombre
                    if rel.id_grado.id_grupo_gramaje
                    else None
                ),
                'cupos': rel.cupos,
                'estado': rel.estado,
            }
            for rel in relaciones
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['grados_ids'] = [item['id_grado'] for item in data.get('grados_atendidos', [])]
        return data

    def validate_grados_ids(self, value):
        unique_ids = list(dict.fromkeys(value))
        existentes = set(
            Grados.objects.filter(pk__in=unique_ids).values_list('id_grado', flat=True)
        )
        faltantes = [gid for gid in unique_ids if gid not in existentes]
        if faltantes:
            raise serializers.ValidationError(
                f"Los siguientes grados no existen: {faltantes}"
            )
        return unique_ids

    def _sincronizar_grados(self, sede_jornada, grados_ids):
        if grados_ids is None:
            return
        ids_objetivo = set(grados_ids)
        actuales = {
            rel.id_grado_id: rel
            for rel in SedeJornadaGrado.objects.filter(id_sede_jornada=sede_jornada)
        }
        # Inactivar o eliminar relaciones removidas; activar/crear las incluidas
        for grado_id, rel in actuales.items():
            if grado_id not in ids_objetivo and rel.estado != 'INACTIVO':
                rel.estado = 'INACTIVO'
                rel.save(update_fields=['estado'])
        for grado_id in grados_ids:
            rel = actuales.get(grado_id)
            if rel:
                if rel.estado != 'ACTIVO':
                    rel.estado = 'ACTIVO'
                    rel.save(update_fields=['estado'])
            else:
                SedeJornadaGrado.objects.create(
                    id_sede_jornada=sede_jornada,
                    id_grado_id=grado_id,
                    estado='ACTIVO',
                )

    def create(self, validated_data):
        grados_ids = validated_data.pop('grados_ids', None)
        with transaction.atomic():
            sede_jornada = super().create(validated_data)
            self._sincronizar_grados(sede_jornada, grados_ids)
        return sede_jornada

    def update(self, instance, validated_data):
        grados_ids = validated_data.pop('grados_ids', None)
        with transaction.atomic():
            sede_jornada = super().update(instance, validated_data)
            self._sincronizar_grados(sede_jornada, grados_ids)
        return sede_jornada
