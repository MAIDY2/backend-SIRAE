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
            "id_usuario_supervisor",
            "supervisor_nombre",
        ]

    def get_supervisor_nombre(self, obj):
        if obj.id_usuario_supervisor:
            return f"{obj.id_usuario_supervisor.nombre} {obj.id_usuario_supervisor.apellido}".strip()
        return None

