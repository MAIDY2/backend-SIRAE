from rest_framework import serializers
from ..models import Institucion, SupervisorInstitucion


class InstitucionSerializer(serializers.ModelSerializer):
    administrador_asignado = serializers.SerializerMethodField()
    supervisor_asignado = serializers.SerializerMethodField()

    class Meta:
        model = Institucion
        fields = '__all__'

    def get_administrador_asignado(self, obj):
        from apps_sirae.usuarios.models import Usuario
        admin = Usuario.objects.filter(
            id_institucion=obj,
            is_active=True,
            rol__nombre__in=['Administrador', 'administrador', 'admin']
        ).first()
        if admin:
            return {
                'id_usuario': admin.id_usuario,
                'nombre_completo': admin.nombre_completo,
                'correo': admin.correo
            }
        return None

    def get_supervisor_asignado(self, obj):
        rel = obj.supervisores_asignados.select_related('id_supervisor').first()
        if rel and rel.id_supervisor and rel.id_supervisor.is_active:
            return {
                'id_usuario': rel.id_supervisor.id_usuario,
                'nombre_completo': rel.id_supervisor.nombre_completo,
                'correo': rel.id_supervisor.correo
            }
        return None


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

    def validate(self, attrs):
        id_inst = attrs.get('id_institucion')
        id_sup = attrs.get('id_supervisor')

        # Regla de negocio PAE: Una institución solo puede tener un único Supervisor responsable
        filtro = SupervisorInstitucion.objects.filter(id_institucion=id_inst)
        if self.instance:
            filtro = filtro.exclude(pk=self.instance.pk)

        rel_existente = filtro.select_related('id_supervisor', 'id_institucion').first()
        if rel_existente:
            sup_nom = rel_existente.id_supervisor.nombre_completo if rel_existente.id_supervisor else f"ID {rel_existente.id_supervisor_id}"
            inst_nom = rel_existente.id_institucion.nombre_institucion if rel_existente.id_institucion else "esta institución"
            raise serializers.ValidationError({
                'id_institucion': f"La institución '{inst_nom}' ya está asignada al Supervisor '{sup_nom}'. Cada institución solo puede tener un único Supervisor responsable."
            })
        return attrs