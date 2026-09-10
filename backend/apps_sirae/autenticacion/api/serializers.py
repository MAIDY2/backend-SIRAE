# -*- coding: utf-8 -*-
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

from apps_sirae.usuarios.models import Usuario


class SolicitarResetPasswordSerializer(serializers.Serializer):
    """
    Recibe el correo del usuario que quiere recuperar su contraseña.
    Siempre responde OK (por seguridad, no revela si el correo existe o no).
    """
    correo = serializers.EmailField()

    def validate_correo(self, value):
        # Guardamos el usuario si existe, pero no lanzamos error si no existe
        self._usuario = Usuario.objects.filter(correo=value, is_active=True).first()
        return value

    def get_usuario(self):
        return getattr(self, '_usuario', None)


class ConfirmarResetPasswordSerializer(serializers.Serializer):
    """
    Recibe uid + token (del enlace enviado por email) y la nueva contraseña.
    """
    uid             = serializers.CharField()
    token           = serializers.CharField()
    password_nuevo  = serializers.CharField(write_only=True, validators=[validate_password])
    password_nuevo2 = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['password_nuevo'] != attrs['password_nuevo2']:
            raise serializers.ValidationError({'password_nuevo2': 'Las contraseñas no coinciden.'})
        return attrs
