import logging
from django.conf import settings
from django.core.mail import send_mail
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.contrib.auth.hashers import check_password, make_password
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from ..models import Usuario
from .serializers import UsuarioSerializer

logger = logging.getLogger(__name__)


class PasswordResetService:
    """
    Servicio para generar y validar tokens de recuperación de contraseñas
    utilizando firmas criptográficas con TimestampSigner de Django.
    """
    SALT = 'sirae-recuperacion-contrasena-pae'
    DURACION_TOKEN_SEGUNDOS = 900  # 15 minutos

    @classmethod
    def generar_token(cls, usuario: Usuario) -> str:
        signer = TimestampSigner(salt=cls.SALT)
        # Se incluye un fragmento del hash de la contraseña actual.
        # Si la contraseña cambia, el token se invalida automáticamente.
        pwd_snippet = str(usuario.password)[-12:] if usuario.password else 'nopwd'
        data_str = f"{usuario.id_usuario}:{usuario.email}:{pwd_snippet}"
        return signer.sign(data_str)

    @classmethod
    def validar_token(cls, token: str):
        signer = TimestampSigner(salt=cls.SALT)
        try:
            data_str = signer.unsign(token, max_age=cls.DURACION_TOKEN_SEGUNDOS)
            partes = data_str.split(':', 2)
            if len(partes) != 3:
                return None, "Estructura del token no válida."

            id_usuario, email, pwd_snippet = partes
            usuario = Usuario.objects.select_related('id_rol').get(id_usuario=id_usuario, email=email)

            actual_snippet = str(usuario.password)[-12:] if usuario.password else 'nopwd'
            if actual_snippet != pwd_snippet:
                return None, "Este enlace o token de recuperación ya fue utilizado previamente."

            if not usuario.is_active:
                return None, "La cuenta de este usuario se encuentra inactiva."

            return usuario, None

        except SignatureExpired:
            return None, "El enlace de recuperación ha caducado (vence en 15 minutos). Por favor solicita uno nuevo."
        except (BadSignature, ValueError, Usuario.DoesNotExist):
            return None, "El enlace o token de recuperación es inválido o está corrupto."


class SolicitarRecuperacionPasswordView(APIView):
    """
    POST /api/auth/password-reset/solicitar/
    Envía un correo con el token y enlace de recuperación al usuario.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip()
        if not email:
            return Response(
                {"error": "Debes proporcionar un correo electrónico válido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            usuario = Usuario.objects.select_related('id_rol').get(email__iexact=email)
        except Usuario.DoesNotExist:
            # Respuesta amigable para evitar enumeración de correos
            return Response(
                {
                    "status": "success",
                    "mensaje": "Si el correo ingresado se encuentra registrado en el sistema SIRAE, recibirás las instrucciones de recuperación.",
                    "email": email
                },
                status=status.HTTP_200_OK
            )

        if not usuario.is_active:
            return Response(
                {"error": "La cuenta asociada a este correo se encuentra inactiva. Contacte al Administrador."},
                status=status.HTTP_403_FORBIDDEN
            )

        token = PasswordResetService.generar_token(usuario)
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        enlace_recuperacion = f"{frontend_url}/recuperar-password?token={token}"

        asunto = "Restablecimiento de Contraseña - Sistema SIRAE PAE"
        mensaje_texto = (
            f"Estimado/a {usuario.nombre_completo},\n\n"
            f"Se ha solicitado el restablecimiento de contraseña para tu cuenta en SIRAE (Programa de Alimentación Escolar).\n\n"
            f"Para crear una nueva contraseña, ingresa al siguiente enlace:\n"
            f"{enlace_recuperacion}\n\n"
            f"O bien, utiliza directamente tu código/token de seguridad:\n"
            f"{token}\n\n"
            f"Este enlace es válido durante 15 minutos.\n"
            f"Si tú no solicitaste este cambio, ignora este mensaje. Tu cuenta continúa protegida.\n\n"
            f"Atentamente,\n"
            f"Equipo de Soporte SIRAE - Sistema 1-2-3 del PAE"
        )

        mensaje_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
            <div style="background-color: #2b6cb0; padding: 15px; border-radius: 6px; text-align: center; color: white;">
                <h2 style="margin: 0;">SIRAE - Sistema 1-2-3 del PAE</h2>
                <p style="margin: 5px 0 0 0; font-size: 14px;">Programa de Alimentación Escolar</p>
            </div>
            <div style="padding: 20px 0;">
                <p>Estimado/a <strong>{usuario.nombre_completo}</strong>,</p>
                <p>Recibimos una solicitud para restablecer la contraseña de acceso a tu cuenta.</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{enlace_recuperacion}" style="background-color: #3182ce; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                        Restablecer Contraseña
                    </a>
                </div>
                <p style="font-size: 13px; color: #4a5568;">O si lo prefieres, copia y pega el siguiente token en la plataforma:</p>
                <div style="background-color: #edf2f7; padding: 10px; border-radius: 4px; font-family: monospace; word-break: break-all; font-size: 12px;">
                    {token}
                </div>
                <p style="font-size: 13px; color: #e53e3e; margin-top: 15px;">
                    <strong>Nota:</strong> Este enlace caducará automáticamente en <strong>15 minutos</strong>.
                </p>
                <p style="font-size: 13px; color: #718096;">
                    Si no fuiste tú quien solicitó este cambio, puedes ignorar este correo de forma segura.
                </p>
            </div>
            <hr style="border: none; border-top: 1px solid #e2e8f0;" />
            <p style="font-size: 11px; color: #a0aec0; text-align: center;">
                SIRAE PAE &copy; 2026 - Plataforma de Gestión y Control Alimentario Escolar
            </p>
        </div>
        """

        try:
            send_mail(
                subject=asunto,
                message=mensaje_texto,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@sirae.edu.co'),
                recipient_list=[usuario.email],
                html_message=mensaje_html,
                fail_silently=False,
            )
            print(f"[SIRAE EMAIL] Correo de recuperacion enviado con exito a: {usuario.email}")
        except Exception as e:
            logger.error(f"[SIRAE EMAIL ERROR] No se pudo enviar el correo a {usuario.email}: {e}", exc_info=True)
            print(f"[SIRAE EMAIL ERROR] Fallo el envio de correo a {usuario.email}: {e}")
            return Response(
                {
                    "error": "No fue posible enviar el correo de recuperación en este momento. Por favor verifica la configuración de correo del servidor o contacta al administrador.",
                    "detalle": str(e) if settings.DEBUG else None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        respuesta = {
            "status": "success",
            "mensaje": "Se han enviado las instrucciones de recuperación al correo electrónico registrado.",
            "email": usuario.email,
        }

        # En modo DEBUG facilitamos el token en la respuesta para agilizar pruebas de desarrollo
        if settings.DEBUG:
            respuesta["debug_token"] = token
            respuesta["debug_link"] = enlace_recuperacion

        return Response(respuesta, status=status.HTTP_200_OK)


class ValidarTokenPasswordView(APIView):
    """
    POST /api/auth/password-reset/validar-token/
    Verifica si un token de recuperación es legítimo y sigue activo.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token', '').strip()
        if not token:
            return Response({"error": "Debes proporcionar el token de recuperación."}, status=status.HTTP_400_BAD_REQUEST)

        usuario, error = PasswordResetService.validar_token(token)
        if error:
            return Response({"valido": False, "error": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "valido": True,
                "mensaje": "Token verificado exitosamente.",
                "email": usuario.email,
                "nombre_completo": usuario.nombre_completo
            },
            status=status.HTTP_200_OK
        )


class ConfirmarRecuperacionPasswordView(APIView):
    """
    POST /api/auth/password-reset/confirmar/
    Aplica la nueva contraseña del usuario una vez validado el token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token', '').strip()
        nueva_password = request.data.get('nueva_password', '').strip()
        confirmar_password = request.data.get('confirmar_password', '').strip()

        if not token:
            return Response({"error": "El token de recuperación es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)

        if not nueva_password or not confirmar_password:
            return Response(
                {"error": "Debes ingresar la nueva contraseña y su confirmación."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if nueva_password != confirmar_password:
            return Response(
                {"error": "Las contraseñas no coinciden. Verifica que ambas sean exactamente iguales."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(nueva_password) < 6:
            return Response(
                {"error": "La nueva contraseña debe tener al menos 6 caracteres."},
                status=status.HTTP_400_BAD_REQUEST
            )

        usuario, error = PasswordResetService.validar_token(token)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        # Hashear y actualizar contraseña
        usuario.password = make_password(nueva_password)
        usuario.save()

        return Response(
            {
                "status": "success",
                "mensaje": "Tu contraseña ha sido restablecida exitosamente. Ya puedes iniciar sesión con tu nueva clave."
            },
            status=status.HTTP_200_OK
        )


class CambiarPasswordView(APIView):
    """
    POST /api/auth/cambiar-password/
    Permite que un usuario con sesión iniciada actualice su contraseña actual.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        usuario = request.user
        password_actual = request.data.get('password_actual', '')
        nueva_password = request.data.get('nueva_password', '').strip()
        confirmar_password = request.data.get('confirmar_password', '').strip()

        if not password_actual or not nueva_password or not confirmar_password:
            return Response(
                {"error": "Todos los campos son obligatorios (contraseña actual, nueva y confirmación)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not check_password(password_actual, usuario.password):
            return Response(
                {"error": "La contraseña actual es incorrecta."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if nueva_password != confirmar_password:
            return Response(
                {"error": "La nueva contraseña y su confirmación no coinciden."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(nueva_password) < 6:
            return Response(
                {"error": "La nueva contraseña debe tener al menos 6 caracteres."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if password_actual == nueva_password:
            return Response(
                {"error": "La nueva contraseña no puede ser idéntica a la anterior."},
                status=status.HTTP_400_BAD_REQUEST
            )

        usuario.password = make_password(nueva_password)
        usuario.save()

        return Response(
            {
                "status": "success",
                "mensaje": "Tu contraseña ha sido actualizada exitosamente."
            },
            status=status.HTTP_200_OK
        )


class PerfilUsuarioView(APIView):
    """
    GET /api/auth/me/
    Retorna la información del usuario autenticado, su rol y estado.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UsuarioSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
