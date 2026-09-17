from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps_sirae.usuarios.models import Usuario


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Serializer personalizado para el Login JWT.
    Guarda 'id_usuario' en el payload para que CustomJWTAuthentication lo reconozca.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Inyecta el ID personalizado de tu modelo Usuario
        token['user_id'] = user.id_usuario
        token['correo'] = user.correo
        
        # Opcional: incluir el rol si lo necesitas en el frontend
        if hasattr(user, 'rol') and user.rol:
            token['rol'] = getattr(user.rol, 'nombre', str(user.rol))

        return token


class UsuarioSerializer(serializers.ModelSerializer):

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
            'password',
            'is_active',
            'is_staff'
        ]

        extra_kwargs = {
            'password': {
                'write_only': True
            }
        }

    def create(self, validated_data):
        password = validated_data.pop('password', None)

        usuario = Usuario(**validated_data)

        if password:
            usuario.set_password(password)

        usuario.save()

        return usuario

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)

        for atributo, valor in validated_data.items():
            setattr(instance, atributo, valor)

        if password:
            instance.set_password(password)

        instance.save()

        return instance