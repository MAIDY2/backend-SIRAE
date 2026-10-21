from rest_framework import serializers
from ..models import Institucion, SupervisorInstitucion


class InstitucionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Institucion
        fields = '__all__'


class SupervisorInstitucionSerializer(serializers.ModelSerializer):
    institucion_nombre = serializers.CharField(source='id_institucion.nombre_institucion', read_only=True)
    supervisor_nombre = serializers.CharField(source='id_supervisor.nombre_completo', read_only=True)

    class Meta:
        model = SupervisorInstitucion
        fields = [
            'id_supervisor_institucion',
            'id_supervisor',
            'supervisor_nombre',
            'id_institucion',
            'institucion_nombre',
            'fecha_asignacion',
        ]