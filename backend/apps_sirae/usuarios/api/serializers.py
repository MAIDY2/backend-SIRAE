from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

from apps_sirae.usuarios.models import Usuario
from apps_sirae.roles.models import Rol
from apps_sirae.roles.api.serializers import RolSerializer


class UsuarioSerializer(serializers.ModelSerializer):
    """Solo lectura: muestra los datos del usuario con su rol completo."""
    rol = RolSerializer(read_only=True)

    class Meta:
        model  = Usuario
        fields = [
            'id_usuario', 'nombre', 'apellido', 'correo',
            'tipo_documento', 'numero_documento', 'rol',
            'is_active', 'is_staff',
        ]


class UsuarioCreateSerializer(serializers.ModelSerializer):
    """Creación de usuario: acepta password y lo hashea automáticamente."""
    password  = serializers.CharField(write_only=True, validators=[validate_password])
    id_rol    = serializers.PrimaryKeyRelatedField(
                    queryset=Rol.objects.all(),
                    source='rol',
                    required=False,
                    allow_null=True
                )

    class Meta:
        model  = Usuario
        fields = [
            'nombre', 'apellido', 'correo',
            'tipo_documento', 'numero_documento',
            'id_rol', 'password',
        ]

    def create(self, validated_data):
        password = validated_data.pop('password')
        user     = Usuario(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UsuarioUpdateSerializer(serializers.ModelSerializer):
    """Actualización parcial de usuario (sin cambiar contraseña aquí)."""
    id_rol = serializers.PrimaryKeyRelatedField(
                 queryset=Rol.objects.all(),
                 source='rol',
                 required=False,
                 allow_null=True
             )

    class Meta:
        model  = Usuario
        fields = [
            'nombre', 'apellido', 'tipo_documento',
            'numero_documento', 'id_rol', 'is_active',
        ]


class CambioPasswordSerializer(serializers.Serializer):
    """Permite cambiar la contraseña del usuario autenticado."""
    password_actual = serializers.CharField(write_only=True)
    password_nuevo  = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_password_actual(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('La contraseña actual es incorrecta.')
        return value
