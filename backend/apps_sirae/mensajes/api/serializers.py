from rest_framework import serializers
from apps_sirae.mensajes.models import Mensaje
from apps_sirae.usuarios.models import Usuario


class MensajeSerializer(serializers.ModelSerializer):
    remitente_nombre = serializers.SerializerMethodField()
    remitente_rol = serializers.SerializerMethodField()
    destinatario_nombre = serializers.SerializerMethodField()
    destinatario_rol = serializers.SerializerMethodField()
    es_emisor = serializers.SerializerMethodField()

    class Meta:
        model = Mensaje
        fields = [
            'id_mensaje',
            'remitente',
            'remitente_nombre',
            'remitente_rol',
            'destinatario',
            'destinatario_nombre',
            'destinatario_rol',
            'contenido_texto',
            'imagen_url',
            'fecha_envio',
            'leido',
            'es_emisor',
        ]
        read_only_fields = ['id_mensaje', 'fecha_envio', 'leido', 'remitente']

    def get_remitente_nombre(self, obj):
        if obj.remitente:
            return f"{obj.remitente.nombre} {obj.remitente.apellido}".strip()
        return ""

    def get_remitente_rol(self, obj):
        if obj.remitente and obj.remitente.rol:
            return obj.remitente.rol.nombre
        return ""

    def get_destinatario_nombre(self, obj):
        if obj.destinatario:
            return f"{obj.destinatario.nombre} {obj.destinatario.apellido}".strip()
        return ""

    def get_destinatario_rol(self, obj):
        if obj.destinatario and obj.destinatario.rol:
            return obj.destinatario.rol.nombre
        return ""

    def get_es_emisor(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            return obj.remitente_id == request.user.id_usuario
        return False


class ContactoChatSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.SerializerMethodField()
    rol = serializers.SerializerMethodField()
    ultimo_mensaje = serializers.CharField(read_only=True, default='')
    ultima_fecha = serializers.DateTimeField(read_only=True, default=None)
    mensajes_no_leidos = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Usuario
        fields = [
            'id_usuario',
            'nombre',
            'apellido',
            'nombre_completo',
            'correo',
            'rol',
            'ultimo_mensaje',
            'ultima_fecha',
            'mensajes_no_leidos',
        ]

    def get_nombre_completo(self, obj):
        return f"{obj.nombre} {obj.apellido}".strip()

    def get_rol(self, obj):
        if obj.rol:
            return obj.rol.nombre
        return ""
