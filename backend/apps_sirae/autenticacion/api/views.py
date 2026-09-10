# -*- coding: utf-8 -*-
import logging

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.conf import settings
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps_sirae.usuarios.models import Usuario
from .serializers import SolicitarResetPasswordSerializer, ConfirmarResetPasswordSerializer

logger = logging.getLogger(__name__)

token_generator = PasswordResetTokenGenerator()


class SolicitarResetPasswordView(APIView):
    """
    POST /api/auth/recuperar-password/
    Body: { "correo": "usuario@ejemplo.com" }

    Envía un email con el enlace de recuperación.
    Siempre responde 200 por seguridad (no revela si el correo existe).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SolicitarResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        usuario = serializer.get_usuario()

        if usuario:
            uid   = urlsafe_base64_encode(force_bytes(usuario.pk))
            token = token_generator.make_token(usuario)
            link  = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"

            try:
                send_mail(
                    subject='Recuperación de contraseña — SIRAE PAE',
                    message=(
                        f'Hola {usuario.get_full_name()},\n\n'
                        f'Recibimos una solicitud para restablecer tu contraseña.\n\n'
                        f'Haz clic en el siguiente enlace (válido por 24 horas):\n{link}\n\n'
                        f'Si no solicitaste esto, ignora este mensaje.\n\n'
                        f'— Equipo SIRAE PAE'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[usuario.correo],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error(f'Error al enviar correo de recuperación a {usuario.correo}: {e}')

        return Response(
            {'detail': 'Si el correo está registrado, recibirás un enlace de recuperación.'},
            status=status.HTTP_200_OK
        )


class ConfirmarResetPasswordView(APIView):
    """
    POST /api/auth/confirmar-password/
    Body: { "uid": "...", "token": "...", "password_nuevo": "...", "password_nuevo2": "..." }

    Valida el token y cambia la contraseña del usuario.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ConfirmarResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            uid      = force_str(urlsafe_base64_decode(serializer.validated_data['uid']))
            usuario  = Usuario.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Usuario.DoesNotExist):
            return Response(
                {'detail': 'El enlace de recuperación no es válido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not token_generator.check_token(usuario, serializer.validated_data['token']):
            return Response(
                {'detail': 'El enlace ha expirado o ya fue utilizado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        usuario.set_password(serializer.validated_data['password_nuevo'])
        usuario.save()

        return Response(
            {'detail': 'Contraseña actualizada correctamente. Ya puedes iniciar sesión.'},
            status=status.HTTP_200_OK
        )
