
from rest_framework import serializers
from ..models import Notificacion


class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = [
            'id_notificacion',
            'id_usuario',
            'id_remitente',
            'titulo',
            'mensaje',
            'imagen_url',
            'fecha_hora',
            'leida',
        ]
        read_only_fields = [
            'id_notificacion',
            'id_remitente',
            'imagen_url',
            'fecha_hora',
            'leida',
        ]
        extra_kwargs = {
            'id_usuario': {'required': False},
        }

    def validate_titulo(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                'El título es obligatorio.'
            )
        return value

    def validate_mensaje(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                'El mensaje es obligatorio.'
            )
        return value

    def validate_id_usuario(self, value):
        request = self.context.get('request')
        usuario = getattr(request, 'user', None)
        usuario_id = getattr(usuario, 'id_usuario', None)

        if value != usuario_id:
            raise serializers.ValidationError(
                'No puedes crear notificaciones directamente '
                'para otro usuario. Utiliza el envío autorizado.'
            )

        return value
