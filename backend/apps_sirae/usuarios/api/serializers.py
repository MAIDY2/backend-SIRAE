from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import check_password
from rest_framework.exceptions import AuthenticationFailed

from apps_sirae.usuarios.models import Usuario
from apps_sirae.roles.api.serializers import RolSerializer


class UsuarioSerializer(serializers.ModelSerializer):
    rol_detalle = RolSerializer(source='rol', read_only=True)

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
        rol = attrs.get('rol')
        if rol and rol.nombre in {'SuperAdministrador', 'Super Administrador'}:
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

        # Validación 3: Solo el Super Administrador puede crear o asignar roles de Administrador o Supervisor
        if rol and rol.nombre in {'Administrador', 'supervisor'}:
            if current_user and not current_user.es_super_administrador():
                raise serializers.ValidationError({
                    'rol': 'Solo el Super Administrador puede crear o asignar los roles de Administrador o Supervisor.'
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
        return token

    def validate(self, attrs):
        correo = attrs.get("correo", "").strip().lower()
        password = attrs.get("password")

        try:
            usuario = Usuario.objects.select_related('rol').get(correo__iexact=correo)
        except Usuario.DoesNotExist:
            raise AuthenticationFailed("No existe ninguna cuenta registrada con este correo.")

        if not usuario.is_active:
            raise AuthenticationFailed("La cuenta del usuario está inactiva.")

        if not check_password(password, usuario.password):
            raise AuthenticationFailed("Contraseña incorrecta.")

        refresh = self.get_token(usuario)

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
                'is_superuser': bool(usuario.is_superuser),
                'debe_cambiar_password': bool(getattr(usuario, 'debe_cambiar_password', False)),
            }
        }