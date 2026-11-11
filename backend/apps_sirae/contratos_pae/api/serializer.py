from rest_framework import serializers

from ..models import Contrato


class ContratoSerializer(serializers.ModelSerializer):
    institucion_nombre = serializers.CharField(source='id_institucion.nombre_institucion', read_only=True)
    sede_nombre = serializers.CharField(source='id_sede.nombre_sede', read_only=True)
    jornada_nombre = serializers.CharField(source='id_jornada.nombre_jornada', read_only=True)
    supervisor_nombre = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Contrato
        fields = [
            "id_contrato",
            "numero_cor",
            "institucion",
            "zona",
            "fecha_inicio",
            "fecha_fin",
            "estado",
            "id_institucion",
            "institucion_nombre",
            "id_sede",
            "sede_nombre",
            "id_jornada",
            "jornada_nombre",
            "cupos",
            "periodicidad_perecederos",
            "dias_cobertura_perecederos",
            "periodicidad_no_perecederos",
            "dias_cobertura_no_perecederos",
            "id_usuario_supervisor",
            "supervisor_nombre",
        ]

    def validate(self, attrs):
        dias_defecto = Contrato.DIAS_POR_PERIODICIDAD
        for per_field, dias_field in (
            ('periodicidad_perecederos', 'dias_cobertura_perecederos'),
            ('periodicidad_no_perecederos', 'dias_cobertura_no_perecederos'),
        ):
            if per_field in attrs and dias_field not in attrs:
                clave = (attrs.get(per_field) or '').upper()
                if clave in dias_defecto:
                    attrs[dias_field] = dias_defecto[clave]
        return super().validate(attrs)

    def get_supervisor_nombre(self, obj):
        if obj.id_usuario_supervisor:
            return f"{obj.id_usuario_supervisor.nombre} {obj.id_usuario_supervisor.apellido}".strip()
        return None

