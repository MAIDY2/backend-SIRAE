# -*- coding: utf-8 -*-
from django.core.cache import cache
from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework.exceptions import AuthenticationFailed


class CustomJWTAuthentication(JWTAuthentication):

    def get_user(self, validated_token):
        jti = validated_token.get('jti')
        token_revocado = bool(
            jti and (
                cache.get(f"revoked_jti:{jti}")
                or BlacklistedToken.objects.filter(token__jti=jti).exists()
            )
        )

        try:
            user_id = validated_token['user_id']
        except KeyError:
            if token_revocado:
                raise InvalidToken('El token ha sido revocado o la sesión fue cerrada.')
            raise InvalidToken('El token no contiene un ID de usuario válido.')

        try:
            user = self.user_model.objects.get(id_usuario=user_id)
        except self.user_model.DoesNotExist:
            raise AuthenticationFailed('Usuario no encontrado.', code='user_not_found')

        if not user.is_active:
            raise AuthenticationFailed(
                'Usuario inactivo. Su cuenta se encuentra desactivada y el token fue revocado.',
                code='user_inactive'
            )

        if token_revocado:
            raise InvalidToken('El token ha sido revocado o la sesión fue cerrada.')

        if user.bloqueado_hasta and user.bloqueado_hasta > timezone.now():
            raise AuthenticationFailed(
                'La cuenta se encuentra bloqueada temporalmente por seguridad.',
                code='user_locked'
            )

        return user
