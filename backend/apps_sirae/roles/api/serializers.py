from rest_framework import serializers
from apps_sirae.roles.models import Rol, RolPermiso, AuditoriaPermisoRol, MATRIZ_MODULOS_SISTEMA


class RolPermisoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolPermiso
        fields = ['id_rol_permiso', 'modulo', 'codigo', 'descripcion', 'creado_en']


class AuditoriaPermisoRolSerializer(serializers.ModelSerializer):
    actor_correo = serializers.SerializerMethodField()
    nombre_rol = serializers.CharField(source='rol.get_nombre_display', read_only=True)

    class Meta:
        model = AuditoriaPermisoRol
        fields = [
            'id_auditoria',
            'rol',
            'nombre_rol',
            'actor_correo',
            'accion',
            'permisos_anteriores',
            'permisos_nuevos',
            'detalle',
            'ip_address',
            'creado_en',
        ]

    def get_actor_correo(self, obj):
        return obj.usuario_actor.correo if obj.usuario_actor else 'Sistema'


class RolSerializer(serializers.ModelSerializer):
    nombre_display = serializers.CharField(source='get_nombre_display', read_only=True)
    es_protegido = serializers.BooleanField(read_only=True)
    permisos = serializers.SerializerMethodField()
    total_usuarios_activos = serializers.SerializerMethodField()
    puede_editar_permisos = serializers.SerializerMethodField()

    class Meta:
        model = Rol
        fields = [
            'id_rol',
            'nombre',
            'nombre_display',
            'descripcion',
            'es_protegido',
            'permisos',
            'total_usuarios_activos',
            'puede_editar_permisos',
        ]

    def get_permisos(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        # Criterios 3 y 7: Mostrar los permisos asociados a cada rol cuando el usuario tenga autorización.
        if user and user.is_authenticated and (user.es_super_administrador() or user.is_superuser or user.es_administrador()):
            return obj.permisos
        return []

    def get_total_usuarios_activos(self, obj):
        # Criterio 11: Protección de roles con usuarios activos
        if hasattr(obj, 'usuarios'):
            return obj.usuarios.filter(is_active=True).count()
        return 0

    def get_puede_editar_permisos(self, obj):
        # Criterio 4: Modificación restringida exclusivamente a Superadministrador
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        return bool(user and user.is_authenticated and (user.es_super_administrador() or user.is_superuser))


class AsignarPermisosRolSerializer(serializers.Serializer):
    permisos = serializers.ListField(
        child=serializers.CharField(max_length=100),
        allow_empty=False,
        help_text="Lista de códigos de permisos a asignar al rol."
    )
