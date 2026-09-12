from django.utils import timezone
from rest_framework import serializers

from ..models import PreparacionAsignada


class PreparacionAsignadaSerializer(serializers.ModelSerializer):
    fecha = serializers.DateField(
        input_formats=['iso-8601', '%d/%m/%Y'],
        required=False,
        default=timezone.localdate,
    )
    id_usuario_manipuladora = serializers.IntegerField(required=False)

    class Meta:
        model = PreparacionAsignada
        fields = [
            "id_preparacion_asignada",
            "id_menu",
            "id_plato",
            "id_usuario_manipuladora",
            "id_turno",
            "fecha",
            "hora_programada",
            "estado_preparacion",
            "observaciones",
        ]

    def validate(self, attrs):
        if 'id_usuario_manipuladora' not in attrs:
            request = self.context.get('request')
            user = getattr(request, 'user', None)
            user_id = getattr(user, 'id_usuario', None)
            if getattr(user, 'is_authenticated', False) and user_id is not None:
                attrs['id_usuario_manipuladora'] = user_id
            elif self.instance is None:
                raise serializers.ValidationError({
                    'id_usuario_manipuladora': 'Este campo es obligatorio.',
                })
        return attrs
     