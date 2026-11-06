
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import check_password
from rest_framework.exceptions import AuthenticationFailed
from django.db.models import Q

from apps_sirae.usuarios.models import Usuario
from apps_sirae.roles.api.serializers import RolSerializer


def instituciones_asignadas_del_supervisor(usuario):
    """
    Devuelve únicamente las instituciones asignadas al supervisor:
    por relación directa, contrato o institución principal.
    """
    if not usuario.es_supervisor():
        return []

    from apps_sirae.contratos_pae.models import Contrato
    from apps_sirae.instituciones.models import Institucion

    institucion_ids = set(
        usuario.instituciones_asignadas.values_list(
            'id_institucion_id',
            flat=True
        )
    )

    institucion_ids.update(
        Contrato.objects.filter(
            id_usuario_supervisor=usuario,
            id_institucion__isnull=False
        ).values_list('id_institucion_id', flat=True)
    )

    if usuario.id_institucion_id:
        institucion_ids.add(usuario.id_institucion_id)

    if not institucion_ids:
        return []

    instituciones = (
        Institucion.objects.filter(pk__in=institucion_ids)
        .prefetch_related('sedes')
        .order_by('id_institucion')
    )

    return [
        {
            'id_institucion': institucion.id_institucion,
            'nombre_institucion': institucion.nombre_institucion,
            'nit': getattr(institucion, 'nit', ''),
            'sedes': [
                {
                    'id_sede': sede.id_sede,
                    'nombre_sede': sede.nombre_sede,
                    'codigo_dane': getattr(sede, 'codigo_dane', None),
                    'direccion': getattr(sede, 'direccion', None),
                }
                for sede in institucion.sedes.all()
            ],
            'representante_legal': getattr(
                institucion, 'representante_legal', None
            ),
            'telefono': getattr(institucion, 'telefono', None),
            'correo_contacto': getattr(institucion, 'correo_contacto', None),
            'estado': getattr(institucion, 'estado', None),
        }
        for institucion in instituciones
    ]


class UsuarioSerializer(serializers.ModelSerializer):
    rol_detalle = RolSerializer(source='rol', read_only=True)
    institucion_nombre = serializers.CharField(
        source='id_institucion.nombre_institucion',
        read_only=True
    )
    sede_nombre = serializers.CharField(
        source='id_sede.nombre_sede',
        read_only=True
    )
    instituciones_supervisor = serializers.SerializerMethodField()

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
            'instituciones_supervisor',
            'password',
            'is_active',
            'is_staff',
            'debe_cambiar_password',
        ]
        extra_kwargs = {
            'password': {
                'write_only': True,
                'required': False
            }
        }

    def get_instituciones_supervisor(self, obj):
        return instituciones_asignadas_del_supervisor(obj)

    def validate(self, attrs):
        request = self.context.get('request')
        current_user = (
            request.user
            if request and request.user.is_authenticated
            else None
        )

        rol = attrs.get('rol') or (
            self.instance.rol if self.instance else None
        )

        rol_nombre = (
            rol.nombre if rol and hasattr(rol, 'nombre') else ''
        ).strip().lower()

        # Nadie puede crear un Super Administrador mediante la API.
        if rol_nombre in {
            'superadministrador',
            'super administrador',
            'super admin'
        }:
            if not self.instance:
                raise serializers.ValidationError({
                    'rol': (
                        'No está permitido registrar nuevos usuarios '
                        'con el rol de Super Administrador.'
                    )
                })

        # Protección del Super Administrador.
        if self.instance and self.instance.es_super_administrador():
            if not current_user or (
                current_user.id_usuario != self.instance.id_usuario
                and not current_user.is_superuser
            ):
                raise serializers.ValidationError(
                    'No tienes permisos para modificar los datos '
                    'del Super Administrador.'
                )

        # Jerarquía para crear usuarios.
        if not self.instance and current_user:
            if current_user.es_super_administrador():
                es_rol_permitido = any(
                    palabra in rol_nombre
                    for palabra in ['admin', 'supervisor', 'coordinador']
                )

                if not es_rol_permitido:
                    raise serializers.ValidationError({
                        'rol': (
                            'El Super Administrador solo puede crear '
                            'usuarios con rol de Administrador o Supervisor.'
                        )
                    })

            elif current_user.es_administrador():
                es_rol_cocina = any(
                    palabra in rol_nombre
                    for palabra in ['manipuladora', 'jefa', 'cocina']
                )

                if not es_rol_cocina:
                    raise serializers.ValidationError({
                        'rol': (
                            'El Administrador solo puede crear usuarios '
                            'de cocina (Manipuladora Jefe o Manipuladoras).'
                        )
                    })

                if current_user.id_institucion_id:
                    attrs['id_institucion'] = current_user.id_institucion

            else:
                raise serializers.ValidationError(
                    'Tu rol no tiene autorización para registrar nuevos usuarios.'
                )

        # Unicidad del Administrador activo por institución.
        es_admin = any(
            palabra in rol_nombre
            for palabra in ['admin', 'administrador']
        )

        id_inst = attrs.get('id_institucion') or (
            self.instance.id_institucion if self.instance else None
        )

        if es_admin and id_inst:
            filtro_admin = Usuario.objects.filter(
                id_institucion=id_inst,
                is_active=True
            ).filter(
                Q(rol__nombre__iexact='Administrador')
                | Q(rol__nombre__iexact='administrador')
                | Q(rol__nombre__iexact='admin')
            )

            if self.instance:
                filtro_admin = filtro_admin.exclude(
                    pk=self.instance.pk
                )

            admin_existente = filtro_admin.first()

            if admin_existente:
                inst_nom = getattr(
                    id_inst,
                    'nombre_institucion',
                    'esta institución'
                )

                raise serializers.ValidationError({
                    'id_institucion': (
                        f"La institución '{inst_nom}' ya tiene asignado "
                        f"al Administrador '{admin_existente.nombre_completo}'. "
                        "Cada institución solo puede tener un único "
                        "Administrador activo."
                    )
                })

        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password', None)

        if not password:
            raise serializers.ValidationError({
                'password': 'La contraseña es requerida.'
            })

        usuario = Usuario(**validated_data)
        usuario.set_password(password)
        usuario.save()

        return usuario

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)

        instance = super().update(instance, validated_data)

        if password:
            instance.set_password(password)
            instance.save(update_fields=['password'])

        return instance


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'correo'

    @staticmethod
    def _rol_para_cliente(user):
        if user.is_superuser:
            return 'Super Administrador'

        return user.rol.nombre if user.rol else None

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
        token['rol'] = cls._rol_para_cliente(user)
        token['is_superuser'] = bool(user.is_superuser)
        token['debe_cambiar_password'] = bool(
            getattr(user, 'debe_cambiar_password', False)
        )
        token['id_institucion'] = user.id_institucion_id
        token['institucion'] = (
            user.id_institucion.nombre_institucion
            if user.id_institucion else None
        )
        token['id_sede'] = user.id_sede_id

        return token

    def validate(self, attrs):
        correo = attrs.get('correo', '').strip().lower()
        password = attrs.get('password')

        try:
            usuario = Usuario.objects.select_related(
                'rol',
                'id_institucion',
                'id_sede'
            ).get(correo__iexact=correo)

        except Usuario.DoesNotExist:
            raise AuthenticationFailed(
                'No existe ninguna cuenta registrada con este correo.'
            )

        if not usuario.is_active:
            raise AuthenticationFailed(
                'La cuenta del usuario está inactiva.'
            )

        if not check_password(password, usuario.password):
            raise AuthenticationFailed('Contraseña incorrecta.')

        refresh = self.get_token(usuario)

        inst_nombre = (
            usuario.id_institucion.nombre_institucion
            if usuario.id_institucion else None
        )

        sede_nombre = (
            usuario.id_sede.nombre_sede
            if usuario.id_sede else None
        )

        instituciones_sup = instituciones_asignadas_del_supervisor(
            usuario
        )

        if not inst_nombre and instituciones_sup:
            inst_nombre = instituciones_sup[0]['nombre_institucion']

        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'usuario': {
                'id_usuario': usuario.id_usuario,
                'nombre': usuario.nombre,
                'apellido': usuario.apellido,
                'correo': usuario.correo,
                'numero_documento': usuario.numero_documento,
                'rol': self._rol_para_cliente(usuario),
                'id_institucion': usuario.id_institucion_id,
                'institucion': inst_nombre,
                'institucion_nombre': inst_nombre,
                'id_sede': usuario.id_sede_id,
                'sede_nombre': sede_nombre,
                'instituciones_supervisor': instituciones_sup,
                'is_superuser': bool(usuario.is_superuser),
                'debe_cambiar_password': bool(
                    getattr(usuario, 'debe_cambiar_password', False)
                ),
            }
        }
