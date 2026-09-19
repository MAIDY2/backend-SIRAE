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
            'is_staff'
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'required': False}
        }

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
                'rol': usuario.rol.nombre if usuario.rol else None
            }
        }