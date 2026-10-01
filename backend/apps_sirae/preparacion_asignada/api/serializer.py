from django.utils import timezone
from rest_framework import serializers

from ..models import PreparacionAsignada


class PreparacionAsignadaSerializer(serializers.ModelSerializer):
    fecha = serializers.DateField(
        input_formats=['iso-8601', '%d/%m/%Y'],
        required=False,
        default=lambda: timezone.now().date(),
    )
    id_menu = serializers.IntegerField(required=False, allow_null=True)
    id_plato = serializers.IntegerField(required=False, allow_null=True)
    id_usuario_manipuladora = serializers.IntegerField(required=False, allow_null=True)
    id_turno = serializers.IntegerField(required=False, allow_null=True)
    estado_preparacion = serializers.CharField(required=False, allow_blank=True, default='Pendiente')

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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for field_name in ['id_menu', 'id_plato', 'id_usuario_manipuladora', 'id_turno']:
            data[field_name] = getattr(instance, f'{field_name}_id', data.get(field_name))
        return data

    def validate(self, attrs):
        if 'id_usuario_manipuladora' not in attrs or attrs.get('id_usuario_manipuladora') is None:
            request = self.context.get('request')
            user = getattr(request, 'user', None)
            user_id = getattr(user, 'id_usuario', None)
            if getattr(user, 'is_authenticated', False) and user_id is not None:
                attrs['id_usuario_manipuladora'] = user_id
        return attrs
     