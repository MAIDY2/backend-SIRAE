import email.utils
import logging
import os
import secrets
import smtplib
from datetime import timedelta
from urllib.parse import urlencode

import requests
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

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
PRODUCTION_BACKEND_URL = "https://backend-sirae-pyim.onrender.com"


def enviar_email_brevo_api(
    destinatario_email: str,
    asunto: str,
    mensaje_texto: str,
    mensaje_html: str | None = None,
    destinatario_nombre: str | None = None,
) -> bool:
    """
    Envía un correo electrónico utilizando directamente la API HTTP REST de Brevo
    (POST https://api.brevo.com/v3/smtp/email), evitando bloqueos de puertos SMTP (587/465/25)
    en plataformas en la nube como Render.
    Si no se encuentra configurado BREVO_API_KEY, realiza un fallback a send_mail de Django.
    """
    brevo_api_key = (
        os.getenv("BREVO_API_KEY", "").strip()
        or getattr(settings, "BREVO_API_KEY", "").strip()
    )

    from_email_raw = getattr(settings, "DEFAULT_FROM_EMAIL", "jhonriveracaicedo@gmail.com")
    parsed_name, parsed_email = email.utils.parseaddr(from_email_raw)
    sender_email = (
        os.getenv("BREVO_SENDER_EMAIL", "").strip()
        or getattr(settings, "BREVO_SENDER_EMAIL", "").strip()
        or parsed_email
        or from_email_raw
    )
    sender_name = parsed_name if parsed_name else "SIRAE PAE"

    if brevo_api_key:
        headers = {
            "accept": "application/json",
            "api-key": brevo_api_key,
            "content-type": "application/json",
        }
        payload = {
            "sender": {
                "name": sender_name,
                "email": sender_email,
            },
            "to": [
                {
                    "email": destinatario_email,
                    "name": destinatario_nombre or destinatario_email,
                }
            ],
            "subject": asunto,
            "textContent": mensaje_texto,
        }
        if mensaje_html:
            payload["htmlContent"] = mensaje_html
        else:
            payload["htmlContent"] = (
                f"<div style='font-family: Arial, sans-serif; white-space: pre-line;'>"
                f"{mensaje_texto}</div>"
            )

        logger.info(
            "Enviando correo a %s vía Brevo HTTP API: %s (Remitente: %s, Asunto: '%s')",
            destinatario_email,
            BREVO_API_URL,
            sender_email,
            asunto,
        )
        response = requests.post(
            BREVO_API_URL,
            headers=headers,
            json=payload,
            timeout=15,
        )
        if response.status_code not in (200, 201, 202):
            error_detail = (
                f"Error en Brevo HTTP API (HTTP {response.status_code}): {response.text}"
            )
            logger.error(
                "Fallo en Brevo HTTP API al enviar correo a %s: %s",
                destinatario_email,
                error_detail,
            )
            raise RuntimeError(error_detail)

        logger.info(
            "Correo enviado exitosamente vía Brevo HTTP API a: %s (HTTP %s). Respuesta: %s",
            destinatario_email,
            response.status_code,
            response.text,
        )
        return True

    # Fallback transparente a send_mail cuando no esté definido BREVO_API_KEY (desarrollo / test)
    logger.info("BREVO_API_KEY no configurado, utilizando Django send_mail...")
    send_mail(
        subject=asunto,
        message=mensaje_texto,
        from_email=from_email_raw,
        recipient_list=[destinatario_email],
        html_message=mensaje_html,
        fail_silently=False,
    )
    return True


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

    def get(self, request):
        return self.post(request)

    def post(self, request):
        correo = request.data.get("correo")
        if correo is None:
            correo = request.data.get("email")
        if correo is None:
            correo = request.query_params.get("correo") or request.query_params.get("email") or ""
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

        expose_code = (
            settings.PASSWORD_RESET_EXPOSE_CODE
            and correo.casefold() in settings.PASSWORD_RESET_EXPOSE_CODE_EMAILS
        )
        brevo_key = (
            os.getenv("BREVO_API_KEY", "").strip()
            or getattr(settings, "BREVO_API_KEY", "").strip()
        )
        email_is_configured = bool(
            settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
            and settings.EMAIL_HOST_USER
            and settings.EMAIL_HOST_PASSWORD
        ) or bool(brevo_key)
        if not settings.DEBUG and not expose_code and not email_is_configured:
            logger.error(
                "No se puede enviar recuperación de contraseña: "
                "el correo de producción no está configurado."
            )
            return Response(
                {
                    "error": (
                        "El servicio de correo no está configurado. "
                        "Contacta al administrador del sistema."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        with transaction.atomic():
            usuario = (
                Usuario.objects.select_for_update()
                .filter(correo__iexact=correo, is_active=True)
                .first()
            )
            if usuario is None and correo.lower() == "jhonriveracaicedo@gmail.com":
                try:
                    from django.core.management import call_command
                    call_command("asegurar_administrador", email=correo)
                    usuario = (
                        Usuario.objects.select_for_update()
                        .filter(correo__iexact=correo, is_active=True)
                        .first()
                    )
                except Exception as err:
                    logger.warning("[SIRAE AUTH] No se pudo asegurar admin: %s", err)

            if usuario is None:
                logger.warning(
                    "[SIRAE AUTH] Solicitud de código para correo inexistente o inactivo: '%s'",
                    correo,
                )
                return self.respuesta_generica()

            codigo_existente = PasswordResetCode.objects.filter(usuario=usuario).first()
            ahora = timezone.now()
            if (
                not settings.DEBUG
                and codigo_existente is not None
                and codigo_existente.creado_en > ahora - self.INTERVALO_SOLICITUD
            ):
                logger.info(
                    "[SIRAE AUTH] Solicitud de código repetida en menos de 1 minuto para '%s'",
                    correo,
                )
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

        if not expose_code:
            try:
                logger.info(f"Enviando correo de recuperación con código a: {usuario.correo}")
                backend_prod_url = getattr(
                    settings,
                    "BACKEND_URL",
                    PRODUCTION_BACKEND_URL,
                ).rstrip("/")
                asunto = "Código para recuperar tu contraseña - SIRAE"
                mensaje_texto = (
                    f"Hola {usuario.nombre_completo},\n\n"
                    f"Tu código para recuperar la contraseña es: {codigo}\n\n"
                    "El código vence en 10 minutos y solo puede utilizarse una vez. "
                    "Si no solicitaste este cambio, ignora este mensaje.\n\n"
                    f"Plataforma SIRAE PAE: {backend_prod_url}"
                )
                mensaje_html = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
                    <div style="background-color: #2b6cb0; padding: 15px; border-radius: 6px; text-align: center; color: white;">
                        <h2 style="margin: 0;">SIRAE - Sistema 1-2-3 del PAE</h2>
                        <p style="margin: 5px 0 0 0; font-size: 14px;">Programa de Alimentación Escolar</p>
                    </div>
                    <div style="padding: 20px 0;">
                        <p>Hola <strong>{usuario.nombre_completo}</strong>,</p>
                        <p>Recibimos una solicitud para recuperar tu contraseña de acceso en la plataforma SIRAE.</p>
                        <p>Tu código de verificación de 6 dígitos es:</p>
                        <div style="text-align: center; margin: 25px 0;">
                            <span style="display: inline-block; font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #2b6cb0; background-color: #edf2f7; padding: 12px 28px; border-radius: 8px; border: 1px dashed #2b6cb0;">
                                {codigo}
                            </span>
                        </div>
                        <p style="font-size: 13px; color: #e53e3e;">
                            <strong>Nota:</strong> Este código vence en <strong>10 minutos</strong> y solo puede utilizarse una vez.
                        </p>
                        <p style="font-size: 13px; color: #718096;">
                            Si tú no solicitaste este cambio, ignora este mensaje de forma segura. Tu cuenta continúa protegida.
                        </p>
                        <div style="margin-top: 25px; text-align: center;">
                            <a href="{backend_prod_url}" style="font-size: 12px; color: #3182ce; text-decoration: none;">
                                Acceder al sistema SIRAE ({backend_prod_url})
                            </a>
                        </div>
                    </div>
                    <hr style="border: none; border-top: 1px solid #e2e8f0;" />
                    <p style="font-size: 11px; color: #a0aec0; text-align: center;">
                        SIRAE PAE &copy; 2026 - Plataforma de Gestión y Control Alimentario Escolar
                    </p>
                </div>
                """
                enviar_email_brevo_api(
                    destinatario_email=usuario.correo,
                    asunto=asunto,
                    mensaje_texto=mensaje_texto,
                    mensaje_html=mensaje_html,
                    destinatario_nombre=usuario.nombre_completo,
                )
                logger.info(f"Correo de recuperación enviado con éxito a: {usuario.correo}")
            except Exception as e:
                logger.error(f"Error al enviar código de recuperación: {e}", exc_info=True)
                PasswordResetCode.objects.filter(usuario=usuario).delete()
                return Response(
                    {
                        "error": (
                            "No fue posible enviar el código de recuperación. "
                            "Verifica la configuración de correo del servidor e inténtalo nuevamente."
                        ),
                        "detalle": str(e),
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        respuesta = self.respuesta_generica()
        if (
            expose_code
            or (
                settings.DEBUG
                and settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"
            )
        ):
            respuesta.data["debug_code"] = codigo
        return respuesta


class ConfirmarCodigoRecuperacionPasswordView(APIView):
    permission_classes = [AllowAny]
    MAX_INTENTOS = 5

    def post(self, request):
        correo = request.data.get("correo")
        if correo is None:
            correo = request.data.get("email", "")
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
            recuperacion.usuario.debe_cambiar_password = False
            recuperacion.usuario.save(update_fields=["password", "debe_cambiar_password"])
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

    def get(self, request):
        return self.post(request)

    def post(self, request):
        email = (
            request.data.get('email')
            or request.data.get('correo')
            or request.query_params.get('email')
            or request.query_params.get('correo')
            or ''
        )
        if not isinstance(email, str):
            email = ''
        email = email.strip()
        if not email:
            return Response(
                {"error": "Debes proporcionar un correo electrónico válido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            validate_email(email)
        except ValidationError:
            return Response(
                {"error": "Debes proporcionar un correo electrónico válido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            usuario = Usuario.objects.select_related('rol').get(correo__iexact=email)
        except Usuario.DoesNotExist:
            if email.lower() == "jhonriveracaicedo@gmail.com":
                try:
                    from django.core.management import call_command
                    call_command("asegurar_administrador", email=email)
                    usuario = Usuario.objects.select_related('rol').get(correo__iexact=email)
                except Exception as err:
                    logger.warning("[SIRAE AUTH] No se pudo asegurar admin: %s", err)
                    usuario = None
            else:
                usuario = None

            if usuario is None:
                logger.warning("[SIRAE AUTH] Solicitud de password-reset para correo inexistente: '%s'", email)
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
        backend_url = getattr(
            settings,
            'BACKEND_URL',
            PRODUCTION_BACKEND_URL,
        ).rstrip('/')
        frontend_url = getattr(settings, 'FRONTEND_URL', '').rstrip('/')
        base_url = frontend_url if frontend_url else backend_url
        if base_url.startswith("http://localhost") and not settings.DEBUG:
            base_url = backend_url

        enlace_recuperacion = (
            f"{base_url}/recuperar-password?"
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
            enviar_email_brevo_api(
                destinatario_email=usuario.correo,
                asunto=asunto,
                mensaje_texto=mensaje_texto,
                mensaje_html=mensaje_html,
                destinatario_nombre=usuario.nombre_completo,
            )
            logger.info(f"[SIRAE EMAIL] Correo de recuperacion enviado con exito a: {usuario.correo}")
            print(f"[SIRAE EMAIL] Correo de recuperacion enviado con exito a: {usuario.correo}")
        except Exception as e:
            logger.error(f"Error Brevo HTTP / Correo: {e}", exc_info=True)
            logger.error(f"[SIRAE EMAIL ERROR] No se pudo enviar el correo a {usuario.correo}: {e}", exc_info=True)
            print(f"[SIRAE EMAIL ERROR] Fallo el envio de correo a {usuario.correo}: {e}")
            return Response(
                {
                    "error": "No fue posible enviar el correo de recuperación en este momento. Por favor verifica la configuración de correo del servidor o contacta al administrador.",
                    "detalle": str(e)
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
        usuario.set_password(nueva_password)
        usuario.debe_cambiar_password = False
        usuario.save(update_fields=["password", "debe_cambiar_password"])

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

        usuario.set_password(nueva_password)
        usuario.debe_cambiar_password = False
        usuario.save(update_fields=["password", "debe_cambiar_password"])

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


class TestEmailView(APIView):
    """
    Endpoint de diagnóstico para validar el estado de la API de Brevo y probar envíos reales.
    GET /api/auth/test-email/
    POST /api/auth/test-email/ con {'email': 'destinatario@correo.com'}
    """
    permission_classes = [AllowAny]

    def get(self, request):
        email_param = request.query_params.get("email") or request.query_params.get("correo")
        if email_param:
            return self._enviar_prueba(email_param.strip())

        brevo_key = (
            os.getenv("BREVO_API_KEY", "").strip()
            or getattr(settings, "BREVO_API_KEY", "").strip()
        )
        masked_key = (
            (brevo_key[:6] + "..." + brevo_key[-4:])
            if len(brevo_key) > 10
            else ("Configurada" if brevo_key else "No configurada")
        )
        from_email_raw = getattr(settings, "DEFAULT_FROM_EMAIL", "jhonriveracaicedo@gmail.com")
        sender_email = (
            os.getenv("BREVO_SENDER_EMAIL", "").strip()
            or getattr(settings, "BREVO_SENDER_EMAIL", "").strip()
            or from_email_raw
        )
        backend_url = getattr(settings, "BACKEND_URL", PRODUCTION_BACKEND_URL)

        # Asegurar cuenta de administrador para pruebas y producción
        admin_correo = "jhonriveracaicedo@gmail.com"
        admin_usuario = Usuario.objects.filter(correo__iexact=admin_correo).first()
        if not admin_usuario:
            try:
                from django.core.management import call_command
                call_command("asegurar_administrador", email=admin_correo)
                admin_usuario = Usuario.objects.filter(correo__iexact=admin_correo).first()
            except Exception as e:
                logger.warning("No se pudo auto-asegurar admin en test-email: %s", e)

        total_usuarios = Usuario.objects.count()

        return Response(
            {
                "status": "ok",
                "servicio": "Diagnóstico de Correo SIRAE PAE",
                "backend_url": backend_url,
                "brevo_api_key_configurada": bool(brevo_key),
                "brevo_api_key_mascara": masked_key,
                "remitente_configurado": sender_email,
                "admin_usuario_registrado": bool(admin_usuario),
                "admin_correo": admin_correo,
                "total_usuarios": total_usuarios,
                "enlace_recuperar_codigo": f"{backend_url}/api/auth/recuperar-password/?correo={admin_correo}",
                "enlace_recuperar_link": f"{backend_url}/api/auth/password-reset/solicitar/?email={admin_correo}",
                "enlace_prueba_rapido": f"{backend_url}/api/auth/test-email/?email={sender_email}",
                "instrucciones": (
                    "Para probar el envío real hacia tu correo, puedes simplemente abrir: "
                    f"{backend_url}/api/auth/test-email/?email=tu-correo@gmail.com "
                    f"o probar recuperación de contraseña directamente con: "
                    f"{backend_url}/api/auth/recuperar-password/?correo={admin_correo}"
                ),
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        destinatario = (
            request.data.get("email")
            or request.data.get("correo")
            or request.query_params.get("email")
            or request.query_params.get("correo")
            or ""
        )
        return self._enviar_prueba(str(destinatario).strip())

    def _enviar_prueba(self, destinatario: str):
        if not destinatario:
            return Response(
                {"error": "Debes proporcionar un correo en el campo 'email' o 'correo'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_email(destinatario)
        except ValidationError:
            return Response(
                {"error": f"El correo '{destinatario}' no tiene un formato válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        backend_url = getattr(settings, "BACKEND_URL", PRODUCTION_BACKEND_URL)
        asunto = "Prueba de Diagnóstico SIRAE PAE - Brevo API"
        mensaje_texto = (
            f"Hola,\n\nEste es un correo de diagnóstico generado desde SIRAE PAE ({backend_url}) "
            "utilizando directamente la API HTTP de Brevo.\n"
            "Si recibes este mensaje, la configuración en Render y Brevo funciona al 100%."
        )
        mensaje_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 550px; margin: 0 auto; border: 1px solid #cbd5e0; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #2b6cb0; color: white; padding: 20px; text-align: center;">
                <h2 style="margin: 0;">SIRAE - Sistema 1-2-3 del PAE</h2>
                <p style="margin: 5px 0 0 0; font-size: 14px;">Diagnóstico de Enlace Brevo HTTP API</p>
            </div>
            <div style="padding: 25px; background-color: #ffffff; color: #2d3748;">
                <h3 style="color: #38a169; margin-top: 0;">¡Conexión y envío exitosos!</h3>
                <p>El backend en Render (<strong>{backend_url}</strong>) logró enviar este correo mediante Brevo HTTP API.</p>
                <p>Los correos de recuperación de contraseña y activación operarán de forma transparente.</p>
            </div>
        </div>
        """

        try:
            enviar_email_brevo_api(
                destinatario_email=destinatario,
                asunto=asunto,
                mensaje_texto=mensaje_texto,
                mensaje_html=mensaje_html,
            )
            return Response(
                {
                    "status": "success",
                    "mensaje": f"Correo de prueba enviado exitosamente a {destinatario} vía Brevo HTTP API.",
                    "backend_url": backend_url,
                    "destinatario": destinatario,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "error": str(e),
                    "mensaje": "Falló el envío a través de Brevo.",
                    "posibles_causas": [
                        "BREVO_API_KEY no está configurada o es incorrecta en Render.",
                        "El remitente (DEFAULT_FROM_EMAIL o BREVO_SENDER_EMAIL) no está verificado en tu cuenta de Brevo (Senders).",
                        "Tu cuenta de Brevo no tiene créditos disponibles o está suspendida.",
                    ],
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
