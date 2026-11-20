import email.utils
import html
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import PasswordResetCode, Usuario
from .serializers import UsuarioSerializer, revocar_sesiones_activas_usuario

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
PRODUCTION_BACKEND_URL = "https://backend-sirae-pyim.onrender.com"


def _obtener_brevo_api_key() -> str:
    return str(getattr(settings, "BREVO_API_KEY", "") or "").strip()


def _smtp_esta_configurado() -> bool:
    return bool(
        getattr(settings, "EMAIL_BACKEND", "")
        == "django.core.mail.backends.smtp.EmailBackend"
        and str(getattr(settings, "EMAIL_HOST_USER", "") or "").strip()
        and str(getattr(settings, "EMAIL_HOST_PASSWORD", "") or "").strip()
    )


def _correo_esta_configurado() -> bool:
    return bool(_obtener_brevo_api_key()) or _smtp_esta_configurado()


def _obtener_remitente_smtp() -> str:
    default_from = str(getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
    smtp_user = str(getattr(settings, "EMAIL_HOST_USER", "") or "").strip()
    if default_from and default_from != "noreply@sirae.local":
        return default_from
    return smtp_user or default_from or "noreply@sirae.local"


def _aplicar_nueva_password_y_limpiar_seguridad(
    usuario: Usuario,
    nueva_password: str,
    *,
    desbloquear_cuenta: bool = True,
) -> None:
    """
    Actualiza la contraseña hasheada, limpia la contraseña visible inicial,
    desactiva la bandera de cambio obligatorio, opcionalmente desbloquea la cuenta
    y revoca todas las sesiones JWT activas del usuario.
    """
    usuario.set_password(nueva_password)
    usuario.debe_cambiar_password = False
    usuario.password_visible = ""
    update_fields = ["password", "debe_cambiar_password", "password_visible"]

    if desbloquear_cuenta:
        usuario.intentos_fallidos_login = 0
        usuario.bloqueado_hasta = None
        usuario.ultimo_intento_fallido = None
        update_fields.extend(
            ["intentos_fallidos_login", "bloqueado_hasta", "ultimo_intento_fallido"]
        )

    usuario.save(update_fields=update_fields)
    revocar_sesiones_activas_usuario(usuario)


def enviar_email_brevo_api(
    destinatario_email: str,
    asunto: str,
    mensaje_texto: str,
    mensaje_html: str | None = None,
    destinatario_nombre: str | None = None,
) -> bool:
    """
    Envía un correo electrónico utilizando:
    1. La API HTTP REST de Brevo si BREVO_API_KEY está configurada en settings.
    2. Django `send_mail` (Gmail SMTP u otro EMAIL_BACKEND configurado) en caso contrario.
    """
    brevo_api_key = _obtener_brevo_api_key()
    from_email_raw = _obtener_remitente_smtp()
    parsed_name, parsed_email = email.utils.parseaddr(from_email_raw)

    if brevo_api_key:
        sender_email = (
            str(getattr(settings, "BREVO_SENDER_EMAIL", "") or "").strip()
            or parsed_email
            or from_email_raw
        )
        sender_name = parsed_name if parsed_name else "SIRAE PAE"

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
            "htmlContent": mensaje_html
            or (
                "<div style='font-family: Arial, sans-serif; white-space: pre-line;'>"
                f"{html.escape(mensaje_texto)}</div>"
            ),
        }

        logger.info(
            "Enviando correo a %s vía Brevo HTTP API (Remitente: %s, Asunto: '%s')",
            destinatario_email,
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
            "Correo enviado exitosamente vía Brevo HTTP API a %s (HTTP %s).",
            destinatario_email,
            response.status_code,
        )
        return True

    logger.info(
        "Enviando correo a %s vía Django EMAIL_BACKEND=%s (host=%s:%s, remitente=%s)",
        destinatario_email,
        getattr(settings, "EMAIL_BACKEND", ""),
        getattr(settings, "EMAIL_HOST", ""),
        getattr(settings, "EMAIL_PORT", ""),
        from_email_raw,
    )
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

    SALT = "sirae-recuperacion-contrasena-pae"
    DURACION_TOKEN_SEGUNDOS = 900  # 15 minutos

    @classmethod
    def generar_token(cls, usuario: Usuario) -> str:
        signer = TimestampSigner(salt=cls.SALT)
        pwd_snippet = str(usuario.password)[-12:] if usuario.password else "nopwd"
        data_str = f"{usuario.id_usuario}:{usuario.correo}:{pwd_snippet}"
        return signer.sign(data_str)

    @classmethod
    def validar_token(cls, token: str):
        signer = TimestampSigner(salt=cls.SALT)
        try:
            data_str = signer.unsign(token, max_age=cls.DURACION_TOKEN_SEGUNDOS)
            partes = data_str.split(":", 2)
            if len(partes) != 3:
                return None, "Estructura del token no válida."

            id_usuario, correo, pwd_snippet = partes
            usuario = Usuario.objects.select_related("rol").get(
                id_usuario=id_usuario,
                correo__iexact=correo,
            )

            actual_snippet = str(usuario.password)[-12:] if usuario.password else "nopwd"
            if actual_snippet != pwd_snippet:
                return (
                    None,
                    "Este enlace o token de recuperación ya fue utilizado previamente.",
                )

            if not usuario.is_active:
                return None, "La cuenta de este usuario se encuentra inactiva."

            return usuario, None

        except SignatureExpired:
            return (
                None,
                "El enlace de recuperación ha caducado (vence en 15 minutos). Por favor solicita uno nuevo.",
            )
        except (BadSignature, ValueError, Usuario.DoesNotExist):
            return (
                None,
                "El enlace o token de recuperación es inválido o está corrupto.",
            )


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
        correo = request.data.get("correo")
        if correo is None:
            correo = request.data.get("email")
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

        expose_code = bool(
            settings.PASSWORD_RESET_EXPOSE_CODE
            and correo.casefold() in settings.PASSWORD_RESET_EXPOSE_CODE_EMAILS
        )
        email_is_configured = _correo_esta_configurado()
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
                    "creado_en": ahora,
                    "expira_en": ahora + self.DURACION_CODIGO,
                    "intentos_fallidos": 0,
                },
            )

        debe_enviar_correo = email_is_configured or (
            settings.DEBUG and not expose_code
        )
        if debe_enviar_correo:
            try:
                logger.info(
                    "Enviando correo de recuperación con código a: %s",
                    usuario.correo,
                )
                backend_prod_url = getattr(
                    settings,
                    "BACKEND_URL",
                    PRODUCTION_BACKEND_URL,
                ).rstrip("/")
                nombre_seguro = html.escape(usuario.nombre_completo)
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
                        <p>Hola <strong>{nombre_seguro}</strong>,</p>
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
                logger.info(
                    "Correo de recuperación enviado con éxito a: %s",
                    usuario.correo,
                )
            except Exception as exc:
                logger.error(
                    "Error al enviar código de recuperación a %s: %s",
                    usuario.correo,
                    exc,
                    exc_info=True,
                )
                PasswordResetCode.objects.filter(usuario=usuario).delete()
                error_payload = {
                    "error": (
                        "No fue posible enviar el código de recuperación al correo. "
                        "Verifica la configuración de correo del servidor e inténtalo nuevamente."
                    )
                }
                if settings.DEBUG:
                    error_payload["detalle"] = str(exc)
                return Response(
                    error_payload,
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        respuesta = self.respuesta_generica()
        if expose_code or (
            settings.DEBUG
            and settings.EMAIL_BACKEND
            == "django.core.mail.backends.console.EmailBackend"
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

        if not all(
            isinstance(value, str)
            for value in (correo, codigo, nueva_password, confirmar_password)
        ):
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
                    {
                        "error": "El código no es válido o ha vencido. Solicita uno nuevo."
                    },
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

            _aplicar_nueva_password_y_limpiar_seguridad(
                recuperacion.usuario,
                nueva_password,
                desbloquear_cuenta=True,
            )
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
    COOLDOWN_SEGUNDOS = 60

    @staticmethod
    def respuesta_generica():
        return Response(
            {
                "status": "success",
                "mensaje": (
                    "Si el correo ingresado se encuentra registrado en el sistema SIRAE, "
                    "recibirás las instrucciones de recuperación."
                ),
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        email_val = request.data.get("email")
        if email_val is None:
            email_val = request.data.get("correo")
        if not isinstance(email_val, str) or not email_val.strip():
            return Response(
                {"error": "Debes proporcionar un correo electrónico válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email_limpio = email_val.strip()
        try:
            validate_email(email_limpio)
        except ValidationError:
            return Response(
                {"error": "Debes proporcionar un correo electrónico válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not settings.DEBUG and not _correo_esta_configurado():
            logger.error(
                "No se puede enviar enlace de recuperación: "
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

        usuario = (
            Usuario.objects.select_related("rol")
            .filter(correo__iexact=email_limpio, is_active=True)
            .first()
        )
        if usuario is None:
            logger.warning(
                "[SIRAE AUTH] Solicitud de password-reset para correo inexistente o inactivo: '%s'",
                email_limpio,
            )
            return self.respuesta_generica()

        cooldown_key = f"password_reset_link_cooldown:{usuario.correo.casefold()}"
        if not settings.DEBUG and cache.get(cooldown_key):
            logger.info(
                "[SIRAE AUTH] Solicitud de enlace repetida en menos de %s s para '%s'",
                self.COOLDOWN_SEGUNDOS,
                usuario.correo,
            )
            return self.respuesta_generica()

        token = PasswordResetService.generar_token(usuario)
        backend_url = getattr(
            settings,
            "BACKEND_URL",
            PRODUCTION_BACKEND_URL,
        ).rstrip("/")
        frontend_url = str(getattr(settings, "FRONTEND_URL", "") or "").rstrip("/")
        base_url = frontend_url if frontend_url else backend_url
        if base_url.startswith("http://localhost") and not settings.DEBUG:
            base_url = backend_url

        enlace_recuperacion = (
            f"{base_url}/recuperar-password?{urlencode({'token': token})}"
        )
        nombre_seguro = html.escape(usuario.nombre_completo)

        asunto = "Restablecimiento de Contraseña - Sistema SIRAE PAE"
        mensaje_texto = (
            f"Estimado/a {usuario.nombre_completo},\n\n"
            "Se ha solicitado el restablecimiento de contraseña para tu cuenta en SIRAE "
            "(Programa de Alimentación Escolar).\n\n"
            "Para crear una nueva contraseña, ingresa al siguiente enlace:\n"
            f"{enlace_recuperacion}\n\n"
            "O bien, utiliza directamente tu código/token de seguridad:\n"
            f"{token}\n\n"
            "Este enlace es válido durante 15 minutos.\n"
            "Si tú no solicitaste este cambio, ignora este mensaje. Tu cuenta continúa protegida.\n\n"
            "Atentamente,\n"
            "Equipo de Soporte SIRAE - Sistema 1-2-3 del PAE"
        )

        mensaje_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
            <div style="background-color: #2b6cb0; padding: 15px; border-radius: 6px; text-align: center; color: white;">
                <h2 style="margin: 0;">SIRAE - Sistema 1-2-3 del PAE</h2>
                <p style="margin: 5px 0 0 0; font-size: 14px;">Programa de Alimentación Escolar</p>
            </div>
            <div style="padding: 20px 0;">
                <p>Estimado/a <strong>{nombre_seguro}</strong>,</p>
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
            if not settings.DEBUG:
                cache.set(cooldown_key, True, timeout=self.COOLDOWN_SEGUNDOS)
            logger.info(
                "[SIRAE EMAIL] Correo de recuperación enviado con éxito a: %s",
                usuario.correo,
            )
        except Exception as exc:
            logger.error(
                "[SIRAE EMAIL ERROR] No se pudo enviar el correo a %s: %s",
                usuario.correo,
                exc,
                exc_info=True,
            )
            error_payload = {
                "error": (
                    "No fue posible enviar el correo de recuperación en este momento. "
                    "Por favor verifica la configuración de correo del servidor o contacta al administrador."
                )
            }
            if settings.DEBUG:
                error_payload["detalle"] = str(exc)
            return Response(
                error_payload,
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        respuesta = self.respuesta_generica()
        if settings.DEBUG:
            respuesta.data["debug_token"] = token
            respuesta.data["debug_link"] = enlace_recuperacion
        return respuesta


class ValidarTokenPasswordView(APIView):
    """
    POST /api/auth/password-reset/validar-token/
    Verifica si un token de recuperación es legítimo y sigue activo.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token", "")
        if not isinstance(token, str) or not token.strip():
            return Response(
                {"error": "Debes proporcionar el token de recuperación."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        usuario, error = PasswordResetService.validar_token(token.strip())
        if error:
            return Response(
                {"valido": False, "error": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "valido": True,
                "mensaje": "Token verificado exitosamente.",
                "email": usuario.correo,
                "nombre_completo": usuario.nombre_completo,
            },
            status=status.HTTP_200_OK,
        )


class ConfirmarRecuperacionPasswordView(APIView):
    """
    POST /api/auth/password-reset/confirmar/
    Aplica la nueva contraseña del usuario una vez validado el token.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token", "")
        nueva_password = request.data.get("nueva_password", "")
        confirmar_password = request.data.get("confirmar_password", "")

        if not all(
            isinstance(value, str)
            for value in (token, nueva_password, confirmar_password)
        ):
            return Response(
                {"error": "Todos los campos son obligatorios y deben ser texto."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = token.strip()
        if not token:
            return Response(
                {"error": "El token de recuperación es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not nueva_password or not confirmar_password:
            return Response(
                {"error": "Debes ingresar la nueva contraseña y su confirmación."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if nueva_password != confirmar_password:
            return Response(
                {
                    "error": "Las contraseñas no coinciden. Verifica que ambas sean exactamente iguales."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        usuario, error = PasswordResetService.validar_token(token)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        try:
            password_validation.validate_password(nueva_password, user=usuario)
        except ValidationError as validation_error:
            return Response(
                {"error": list(validation_error.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _aplicar_nueva_password_y_limpiar_seguridad(
            usuario,
            nueva_password,
            desbloquear_cuenta=True,
        )

        return Response(
            {
                "status": "success",
                "mensaje": "Tu contraseña ha sido restablecida exitosamente. Ya puedes iniciar sesión con tu nueva clave.",
            },
            status=status.HTTP_200_OK,
        )


class CambiarPasswordView(APIView):
    """
    POST /api/auth/cambiar-password/
    Permite que un usuario con sesión iniciada actualice su contraseña actual.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        usuario = request.user
        password_actual = request.data.get("password_actual", "")
        nueva_password = request.data.get("nueva_password", "")
        confirmar_password = request.data.get("confirmar_password", "")

        if not all(
            isinstance(value, str)
            for value in (password_actual, nueva_password, confirmar_password)
        ):
            return Response(
                {"error": "Todos los campos son obligatorios y deben ser texto."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not password_actual or not nueva_password or not confirmar_password:
            return Response(
                {
                    "error": "Todos los campos son obligatorios (contraseña actual, nueva y confirmación)."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not check_password(password_actual, usuario.password):
            return Response(
                {"error": "La contraseña actual es incorrecta."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if nueva_password != confirmar_password:
            return Response(
                {"error": "La nueva contraseña y su confirmación no coinciden."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if password_actual == nueva_password:
            return Response(
                {"error": "La nueva contraseña no puede ser idéntica a la anterior."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            password_validation.validate_password(nueva_password, user=usuario)
        except ValidationError as validation_error:
            return Response(
                {"error": list(validation_error.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _aplicar_nueva_password_y_limpiar_seguridad(
            usuario,
            nueva_password,
            desbloquear_cuenta=False,
        )

        return Response(
            {
                "status": "success",
                "mensaje": "Tu contraseña ha sido actualizada exitosamente.",
            },
            status=status.HTTP_200_OK,
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


class _EsAdminParaDiagnosticoCorreo(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(
            user.is_staff
            or user.is_superuser
            or user.es_administrador()
            or user.es_super_administrador()
        )


class TestEmailView(APIView):
    """
    Endpoint de diagnóstico (solo administradores) para validar la configuración
    de correo (Gmail SMTP / Brevo HTTP API) y probar envíos reales.
    GET /api/auth/test-email/
    POST /api/auth/test-email/ con {'email': 'destinatario@correo.com'}
    """

    permission_classes = [IsAuthenticated, _EsAdminParaDiagnosticoCorreo]

    def get(self, request):
        brevo_configurado = bool(_obtener_brevo_api_key())
        smtp_configurado = _smtp_esta_configurado()
        backend_url = getattr(settings, "BACKEND_URL", PRODUCTION_BACKEND_URL)
        transporte = (
            "Brevo HTTP API"
            if brevo_configurado
            else f"SMTP ({getattr(settings, 'EMAIL_HOST', '')}:{getattr(settings, 'EMAIL_PORT', '')})"
        )

        return Response(
            {
                "status": "ok",
                "servicio": "Diagnóstico de Correo SIRAE PAE",
                "backend_url": backend_url,
                "transporte_activo": transporte,
                "brevo_api_key_configurada": brevo_configurado,
                "smtp_configurado": smtp_configurado,
                "email_host": getattr(settings, "EMAIL_HOST", ""),
                "email_port": getattr(settings, "EMAIL_PORT", ""),
                "remitente_configurado": _obtener_remitente_smtp(),
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        destinatario = request.data.get("email")
        if destinatario is None:
            destinatario = request.data.get("correo", "")
        if not isinstance(destinatario, str) or not destinatario.strip():
            return Response(
                {"error": "Debes proporcionar un correo en el campo 'email' o 'correo'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        destinatario = destinatario.strip()
        try:
            validate_email(destinatario)
        except ValidationError:
            return Response(
                {"error": f"El correo '{destinatario}' no tiene un formato válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        backend_url = getattr(settings, "BACKEND_URL", PRODUCTION_BACKEND_URL)
        transporte = (
            "Brevo HTTP API"
            if _obtener_brevo_api_key()
            else f"Gmail/SMTP ({getattr(settings, 'EMAIL_HOST', '')})"
        )
        asunto = f"Prueba de Diagnóstico SIRAE PAE - {transporte}"
        mensaje_texto = (
            f"Hola,\n\nEste es un correo de diagnóstico generado desde SIRAE PAE ({backend_url}) "
            f"utilizando {transporte}.\n"
            "Si recibes este mensaje, la configuración de correo funciona correctamente."
        )
        mensaje_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 550px; margin: 0 auto; border: 1px solid #cbd5e0; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #2b6cb0; color: white; padding: 20px; text-align: center;">
                <h2 style="margin: 0;">SIRAE - Sistema 1-2-3 del PAE</h2>
                <p style="margin: 5px 0 0 0; font-size: 14px;">Diagnóstico de Correo ({html.escape(transporte)})</p>
            </div>
            <div style="padding: 25px; background-color: #ffffff; color: #2d3748;">
                <h3 style="color: #38a169; margin-top: 0;">¡Conexión y envío exitosos!</h3>
                <p>El backend (<strong>{html.escape(backend_url)}</strong>) logró enviar este correo mediante <strong>{html.escape(transporte)}</strong>.</p>
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
                    "mensaje": f"Correo de prueba enviado exitosamente a {destinatario} vía {transporte}.",
                    "transporte": transporte,
                    "backend_url": backend_url,
                    "destinatario": destinatario,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            logger.error("Fallo envío de correo de prueba: %s", exc, exc_info=True)
            payload = {
                "status": "error",
                "mensaje": f"Falló el envío a través de {transporte}.",
                "posibles_causas": [
                    "Gmail SMTP: verifica EMAIL_HOST_USER y que EMAIL_HOST_PASSWORD sea una Contraseña de Aplicación de 16 caracteres (con 2FA activo).",
                    "Gmail SMTP: confirma EMAIL_HOST=smtp.gmail.com, EMAIL_PORT=587 y EMAIL_USE_TLS=True.",
                    "Brevo (si usas BREVO_API_KEY): verifica la clave y que el remitente esté validado en Brevo.",
                ],
            }
            if settings.DEBUG:
                payload["error"] = str(exc)
            return Response(payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
