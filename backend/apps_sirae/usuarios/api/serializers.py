from rest_framework import serializers

from apps_sirae.usuarios.models import Usuario


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