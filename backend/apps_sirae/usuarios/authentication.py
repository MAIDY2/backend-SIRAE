from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from rest_framework_simplejwt.settings import api_settings
from .models import Usuario


class CustomJWTAuthentication(JWTAuthentication):
    """
    Autenticación JWT personalizada para SIRAE.
    Busca al usuario autenticado directamente en la tabla 'usuarios'
    utilizando 'id_usuario' en lugar del modelo estándar de Django.
    """

    def get_user(self, validated_token):
        user_id = validated_token.get(api_settings.USER_ID_CLAIM, None)
        if user_id is None:
            raise InvalidToken("El token no contiene un identificador de usuario válido.")

        try:
            usuario = Usuario.objects.select_related('id_rol').get(id_usuario=user_id)
        except Usuario.DoesNotExist:
            raise AuthenticationFailed("El usuario asociado a este token no existe.")

        if not usuario.is_active:
            raise AuthenticationFailed("La cuenta del usuario está inactiva.")

        return usuario
