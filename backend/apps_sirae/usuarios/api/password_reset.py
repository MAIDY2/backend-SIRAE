import logging
from urllib.parse import urlencode
import secrets
import smtplib
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from ..models import PasswordResetCode, Usuario
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
        pwd_snippet = str(usuario.password)[-12:] if usuario.password else 'nopwd'
        data_str = f"{usuario.id_usuario}:{usuario.correo}:{pwd_snippet}"
        return signer.sign(data_str)

    @classmethod
    def validar_token(cls, token: str):
        signer = TimestampSigner(salt=cls.SALT)
        try:
            data_str = signer.unsign(token, max_age=cls.DURACION_TOKEN_SEGUNDOS)
            partes = data_str.split(':', 2)
            if len(partes) != 3:
                return None, "Estructura del token no válida."

            id_usuario, correo, pwd_snippet = partes
            usuario = Usuario.objects.select_related('rol').get(id_usuario=id_usuario, correo__iexact=correo)

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


class SolicitarCodigoRecuperacionPasswordView(APIView):
    permission_classes = [AllowAny]
    DURACION_CODIGO = timedelta(minutes=10)
    INTERVALO_SOLICITUD = timedelta(minutes=1)

    @staticmethod
    def respuesta_generica():
        return Response(
            {
                "mensaje": (
                    "Si el correo está registrado, recibirás un código de "
                    "verificación para recuperar tu contraseña."
                )
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        correo = request.data.get("correo", "")
        if not isinstance(correo, str) or not correo.strip():
            return Response(
                {"error": "Debes proporcionar un correo electrónico válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        correo = correo.strip()
        try:
            validate_email(correo)
        except ValidationError:
            return Response(
                {"error": "Debes proporcionar un correo electrónico válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            usuario = (
                Usuario.objects.select_for_update()
                .filter(correo__iexact=correo, is_active=True)
                .first()
            )
            if usuario is None:
                return self.respuesta_generica()

            codigo_existente = PasswordResetCode.objects.filter(usuario=usuario).first()
            ahora = timezone.now()
            if (
                codigo_existente is not None
                and codigo_existente.creado_en > ahora - self.INTERVALO_SOLICITUD
            ):
                return self.respuesta_generica()

            codigo = f"{secrets.randbelow(1_000_000):06d}"
            PasswordResetCode.objects.update_or_create(
                usuario=usuario,
                defaults={
                    "codigo_hash": make_password(codigo),
                    "expira_en": ahora + self.DURACION_CODIGO,
                    "intentos_fallidos": 0,
                },
            )

        try:
            send_mail(
                subject="Código para recuperar tu contraseña - SIRAE",
                message=(
                    f"Hola {usuario.nombre_completo},\n\n"
                    f"Tu código para recuperar la contraseña es: {codigo}\n\n"
                    "El código vence en 10 minutos y solo puede utilizarse una vez. "
                    "Si no solicitaste este cambio, ignora este mensaje."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[usuario.correo],
                fail_silently=False,
            )
        except (OSError, smtplib.SMTPException):
            logger.exception("No se pudo enviar el código de recuperación de contraseña.")
            PasswordResetCode.objects.filter(usuario=usuario).delete()
            return Response(
                {
                    "error": (
                        "No fue posible enviar el código de recuperación. "
                        "Verifica la configuración de correo del servidor e inténtalo nuevamente."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        respuesta = self.respuesta_generica()
        if (
            settings.DEBUG
            and settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"
        ):
            respuesta.data["debug_code"] = codigo
        return respuesta


class ConfirmarCodigoRecuperacionPasswordView(APIView):
    permission_classes = [AllowAny]
    MAX_INTENTOS = 5

    def post(self, request):
        correo = request.data.get("correo", "")
        codigo = request.data.get("codigo", "")
        nueva_password = request.data.get("nueva_password", "")
        confirmar_password = request.data.get("confirmar_password", "")

        if not all(isinstance(value, str) for value in (
            correo, codigo, nueva_password, confirmar_password
        )):
            return Response(
                {"error": "Todos los campos son obligatorios y deben ser texto."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        correo = correo.strip()
        codigo = codigo.strip()
        if not correo or len(codigo) != 6 or not codigo.isdigit():
            return Response(
                {"error": "El correo o el código de verificación no son válidos."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not nueva_password or not confirmar_password:
            return Response(
                {"error": "Debes ingresar y confirmar la nueva contraseña."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if nueva_password != confirmar_password:
            return Response(
                {"error": "Las contraseñas no coinciden."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_email(correo)
        except ValidationError:
            return Response(
                {"error": "El correo o el código de verificación no son válidos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            try:
                recuperacion = (
                    PasswordResetCode.objects.select_for_update()
                    .select_related("usuario")
                    .get(usuario__correo__iexact=correo, usuario__is_active=True)
                )
            except PasswordResetCode.DoesNotExist:
                return Response(
                    {"error": "El código no es válido o ha vencido. Solicita uno nuevo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if recuperacion.expira_en <= timezone.now():
                recuperacion.delete()
                return Response(
                    {"error": "El código ha vencido. Solicita uno nuevo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if recuperacion.intentos_fallidos >= self.MAX_INTENTOS:
                recuperacion.delete()
                return Response(
                    {"error": "Se agotaron los intentos. Solicita un código nuevo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not check_password(codigo, recuperacion.codigo_hash):
                recuperacion.intentos_fallidos += 1
                if recuperacion.intentos_fallidos >= self.MAX_INTENTOS:
                    recuperacion.delete()
                    mensaje = "Se agotaron los intentos. Solicita un código nuevo."
                else:
                    recuperacion.save(update_fields=["intentos_fallidos"])
                    mensaje = "El código no es válido."
                return Response(
                    {"error": mensaje},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                password_validation.validate_password(
                    nueva_password,
                    user=recuperacion.usuario,
                )
            except ValidationError as error:
                return Response(
                    {"error": list(error.messages)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            recuperacion.usuario.set_password(nueva_password)
            recuperacion.usuario.save(update_fields=["password"])
            recuperacion.delete()

        return Response(
            {"mensaje": "Contraseña restablecida. Ya puedes iniciar sesión."},
            status=status.HTTP_200_OK,
        )


class SolicitarRecuperacionPasswordView(APIView):
    """
    POST /api/auth/password-reset/solicitar/
    Envía un correo con el token y enlace de recuperación al usuario.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email') or request.data.get('correo') or ''
        if not isinstance(email, str):
            email = ''
        email = email.strip()
        if not email:
            return Response(
                {"error": "Debes proporcionar un correo electrónico válido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            usuario = Usuario.objects.select_related('rol').get(correo__iexact=email)
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
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:4200')
        enlace_recuperacion = (
            f"{frontend_url}/recuperar-password?"
            f"{urlencode({'token': token})}"
        )

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
                recipient_list=[usuario.correo],
                html_message=mensaje_html,
                fail_silently=False,
            )
            print(f"[SIRAE EMAIL] Correo de recuperacion enviado con exito a: {usuario.correo}")
        except Exception as e:
            logger.error(f"[SIRAE EMAIL ERROR] No se pudo enviar el correo a {usuario.correo}: {e}", exc_info=True)
            print(f"[SIRAE EMAIL ERROR] Fallo el envio de correo a {usuario.correo}: {e}")
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
            "email": usuario.correo,
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
                "email": usuario.correo,
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
