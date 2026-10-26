from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import check_password
from rest_framework.exceptions import AuthenticationFailed

from apps_sirae.usuarios.models import Usuario
from apps_sirae.roles.api.serializers import RolSerializer


class UsuarioSerializer(serializers.ModelSerializer):
    rol_detalle = RolSerializer(source='rol', read_only=True)
    institucion_nombre = serializers.CharField(source='id_institucion.nombre_institucion', read_only=True)
    sede_nombre = serializers.CharField(source='id_sede.nombre_sede', read_only=True)

    class Meta:
        model = Usuario
        fields = [
            'id_usuario',
            'nombre',
            'apellido',
            'correo',
            'tipo_documento',
            'numero_documento',
            'rol',
            'rol_detalle',
            'id_institucion',
            'institucion_nombre',
            'id_sede',
            'sede_nombre',
            'password',
            'is_active',
            'is_staff',
            'debe_cambiar_password',
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'required': False}
        }
    def validate(self, attrs):
                request = self.context.get('request')
                current_user = request.user if request and request.user.is_authenticated else None

                # Validación 1: Nadie puede crear un Super Administrador por la API (solo seeder/management command)
                rol = attrs.get('rol') or (self.instance.rol if self.instance else None)
                rol_nombre = (rol.nombre if rol and hasattr(rol, 'nombre') else '').strip().lower()

                if rol_nombre in {'superadministrador', 'super administrador', 'super admin'}:
                    if not self.instance:
                        raise serializers.ValidationError({
                            'rol': 'No está permitido registrar nuevos usuarios con el rol de Super Administrador.'
                        })

                # Validación 2: Proteger al Super Administrador de ser editado por otros roles
                if self.instance and self.instance.es_super_administrador():
                    if not current_user or (current_user.id_usuario != self.instance.id_usuario and not current_user.is_superuser):
                        raise serializers.ValidationError(
                            'No tienes permisos para modificar los datos del Super Administrador.'
                        )

                # Validación 3: Jerarquía estricta al crear nuevos usuarios
                if not self.instance and current_user:
                    if current_user.es_super_administrador():
                        # Super Admin solo crea Administradores y Supervisores
                        es_rol_permitido = any(r in rol_nombre for r in ['admin', 'supervisor', 'coordinador'])
                        if not es_rol_permitido:
                            raise serializers.ValidationError({
                                'rol': 'El Super Administrador solo puede crear usuarios con rol de Administrador o Supervisor.'
                            })
                    elif current_user.es_administrador():
                        # Administrador solo crea personal de cocina (Manipuladoras y Manipuladora Jefe)
                        es_rol_cocina = any(r in rol_nombre for r in ['manipuladora', 'jefa', 'cocina'])
                        if not es_rol_cocina:
                            raise serializers.ValidationError({
                                'rol': 'El Administrador solo puede crear usuarios de cocina (Manipuladora Jefe o Manipuladoras).'
                            })
                        # Asigna automáticamente su misma institución
                        if current_user.id_institucion_id:
                            attrs['id_institucion'] = current_user.id_institucion
                    else:
                        raise serializers.ValidationError(
                            'Tu rol no tiene autorización para registrar nuevos usuarios.'
                        )

                # Validación 4: Unicidad de Administrador por Institución
                # Una institución solo puede tener un único Administrador activo
                es_admin = any(r in rol_nombre for r in ['admin', 'administrador'])
                id_inst = attrs.get('id_institucion') or (self.instance.id_institucion if self.instance else None)
                if es_admin and id_inst:
                    filtro_admin = Usuario.objects.filter(
                        id_institucion=id_inst,
                        is_active=True,
                        rol__nombre__in=['Administrador', 'administrador', 'admin']
                    )
                    if self.instance:
                        filtro_admin = filtro_admin.exclude(pk=self.instance.pk)
                    admin_existente = filtro_admin.first()
                    if admin_existente:
                        inst_nom = id_inst.nombre_institucion if hasattr(id_inst, 'nombre_institucion') else 'esta institución'
                        raise serializers.ValidationError({
                            'id_institucion': f"La institución '{inst_nom}' ya tiene asignado al Administrador '{admin_existente.nombre_completo}'. Cada institución solo puede tener un único Administrador activo."
                        })

                return attrs

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        usuario = Usuario(**validated_data)
        if password:
            usuario.set_password(password)
        else:
            raise serializers.ValidationError({"password": "La contraseña es requerida."})
        usuario.save()
        return usuario

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        
        # Actualizar los demás campos normalmente
        instance = super().update(instance, validated_data)
        
        # Si se envió una nueva contraseña, hashearla y guardarla
        if password:
            instance.set_password(password)
            instance.save()
            
        return instance


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'correo'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['correo'] = serializers.CharField()
        if 'username' in self.fields:
            del self.fields['username']

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['id_usuario'] = user.id_usuario
        token['correo'] = user.correo
        token['nombre'] = user.nombre
        token['rol'] = user.rol.nombre if user.rol else None
        token['is_superuser'] = bool(user.is_superuser)
        token['debe_cambiar_password'] = bool(getattr(user, 'debe_cambiar_password', False))
        token['id_institucion'] = user.id_institucion_id
        token['institucion'] = user.id_institucion.nombre_institucion if user.id_institucion else None
        token['id_sede'] = user.id_sede_id
        return token

    def validate(self, attrs):
        correo = attrs.get("correo", "").strip().lower()
        password = attrs.get("password")

        try:
            usuario = Usuario.objects.select_related('rol', 'id_institucion', 'id_sede').get(correo__iexact=correo)
        except Usuario.DoesNotExist:
            raise AuthenticationFailed("No existe ninguna cuenta registrada con este correo.")

        if not usuario.is_active:
            raise AuthenticationFailed("La cuenta del usuario está inactiva.")

        if not check_password(password, usuario.password):
            raise AuthenticationFailed("Contraseña incorrecta.")

        refresh = self.get_token(usuario)

        inst_nombre = usuario.id_institucion.nombre_institucion if usuario.id_institucion else None
        sede_nombre = usuario.id_sede.nombre_sede if usuario.id_sede else None

        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'usuario': {
                'id_usuario': usuario.id_usuario,
                'nombre': usuario.nombre,
                'apellido': usuario.apellido,
                'correo': usuario.correo,
                'numero_documento': usuario.numero_documento,
                'rol': usuario.rol.nombre if usuario.rol else None,
                'id_institucion': usuario.id_institucion_id,
                'institucion': inst_nombre,
                'institucion_nombre': inst_nombre,
                'id_sede': usuario.id_sede_id,
                'sede_nombre': sede_nombre,
                'is_superuser': bool(usuario.is_superuser),
                'debe_cambiar_password': bool(getattr(usuario, 'debe_cambiar_password', False)),
            }
        }