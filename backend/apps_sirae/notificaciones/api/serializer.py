from rest_framework import serializers

from ..models import Notificacion


class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = [
            'id_notificacion',
            'id_usuario',
            'titulo',
            'mensaje',
            'fecha_hora',
            'leida',
        ]
        read_only_fields = ['id_notificacion']
        extra_kwargs = {
            'id_usuario': {'required': False},
        }

    def validate_titulo(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El título es obligatorio.')
        return value

    def validate_mensaje(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El mensaje es obligatorio.')
        return value

    def validate_id_usuario(self, value):
        request = self.context.get('request')
        usuario = getattr(request, 'user', None)
        es_administrador = getattr(usuario, 'es_administrador', lambda: False)
        usuario_id = getattr(usuario, 'id_usuario', None)

        if usuario_id and value != usuario_id and not es_administrador():
            raise serializers.ValidationError(
                'No puedes asignar una notificación a otro usuario.'
            )
        return value