# -*- coding: utf-8 -*-
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework.exceptions import AuthenticationFailed


class CustomJWTAuthentication(JWTAuthentication):

    

    def get_user(self, validated_token):
        try:
            user_id = validated_token['user_id']
        except KeyError:
            raise InvalidToken('El token no contiene un ID de usuario válido.')

        try:
            user = self.user_model.objects.get(id_usuario=user_id)
        except self.user_model.DoesNotExist:
            raise AuthenticationFailed('Usuario no encontrado.', code='user_not_found')

        if not user.is_active:
            raise AuthenticationFailed('Usuario inactivo.', code='user_inactive')

        return user
