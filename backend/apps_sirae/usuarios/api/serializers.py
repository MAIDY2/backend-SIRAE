from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import check_password, make_password
from rest_framework.exceptions import AuthenticationFailed
from ..models import Usuario, Rol


class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = [
            'id_rol',
            'nombre_rol',
            'descripcion'
        ]


class UsuarioSerializer(serializers.ModelSerializer):
    rol = RolSerializer(source='id_rol', read_only=True)
    id_rol = serializers.PrimaryKeyRelatedField(
        queryset=Rol.objects.all(),
        required=True
    )

    class Meta:
        model = Usuario
        fields = [
            'id_usuario',
            'id_rol',
            'rol',
            'nombre_completo',
            'documento_identidad',
            'email',
            'password',
            'estado'
        ]
        extra_kwargs = {
            'password': {
                'write_only': True,
                'required': False
            }
        }

    def validate_email(self, value):
        email = value.strip().lower()
        qs = Usuario.objects.filter(email__iexact=email)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un usuario registrado con este correo electrónico.")
        return email

    def validate_documento_identidad(self, value):
        doc = value.strip()
        qs = Usuario.objects.filter(documento_identidad=doc)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un usuario registrado con este documento de identidad.")
        return doc

    def validate(self, attrs):
        if not self.instance and not attrs.get('password'):
            raise serializers.ValidationError({"password": "La contraseña es requerida para registrar un nuevo usuario."})
        return attrs

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        if 'estado' not in validated_data or not validated_data['estado']:
            validated_data['estado'] = 'Activo'
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'password' in validated_data and validated_data['password']:
            validated_data['password'] = make_password(validated_data['password'])
        else:
            validated_data.pop('password', None)
        return super().update(instance, validated_data)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'] = serializers.CharField()
        if 'username' in self.fields:
            del self.fields['username']

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['id_usuario'] = user.id_usuario
        token['email'] = user.email
        token['nombre_completo'] = user.nombre_completo
        token['id_rol'] = user.id_rol.id_rol if user.id_rol else None
        token['nombre_rol'] = user.rol_nombre
        return token

    def validate(self, attrs):
        email = attrs.get("email", "").strip().lower()
        password = attrs.get("password")

        try:
            usuario = Usuario.objects.select_related('id_rol').get(email__iexact=email)
        except Usuario.DoesNotExist:
            raise AuthenticationFailed("No existe ninguna cuenta registrada con este correo.")

        if not usuario.is_active:
            raise AuthenticationFailed("La cuenta del usuario está inactiva. Comuníquese con el Administrador.")

        if not check_password(password, usuario.password):
            raise AuthenticationFailed("Contraseña incorrecta.")

        refresh = self.get_token(usuario)

        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'usuario': {
                'id_usuario': usuario.id_usuario,
                'nombre_completo': usuario.nombre_completo,
                'email': usuario.email,
                'documento_identidad': usuario.documento_identidad,
                'estado': usuario.estado,
                'rol': {
                    'id_rol': usuario.id_rol.id_rol if usuario.id_rol else None,
                    'nombre_rol': usuario.rol_nombre,
                    'descripcion': usuario.id_rol.descripcion if usuario.id_rol else None
                }
            }
        }