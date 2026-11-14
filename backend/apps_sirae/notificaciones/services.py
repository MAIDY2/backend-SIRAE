import logging
import smtplib
import socket
from typing import Iterable, Sequence

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.html import escape

logger = logging.getLogger(__name__)


def construir_plantilla_notificacion_html(
    titulo: str,
    mensaje: str,
    remitente_nombre: str = "",
    remitente_rol: str = "",
    imagen_url: str | None = None,
    categoria: str = "NOTIFICACIÓN GENERAL",
    enlace_accion: str | None = None,
    texto_accion: str = "Ir a SIRAE",
) -> str:
    """
    Construye una plantilla HTML responsiva y accesible para notificaciones de SIRAE PAE.
    """
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:4200")
    enlace_final = enlace_accion or f"{frontend_url}/notificaciones"

    seccion_remitente = ""
    if remitente_nombre:
        rol_txt = f" ({remitente_rol})" if remitente_rol else ""
        seccion_remitente = f"""
        <div style="margin-bottom: 16px; padding: 10px 14px; background-color: #f7fafc; border-left: 4px solid #3182ce; border-radius: 4px;">
            <p style="margin: 0; font-size: 13px; color: #4a5568;">
                <strong>Enviado por:</strong> {escape(remitente_nombre)}{escape(rol_txt)}
            </p>
        </div>
        """

    seccion_imagen = ""
    if imagen_url:
        seccion_imagen = f"""
        <div style="margin: 18px 0; text-align: center;">
            <img src="{escape(imagen_url)}" alt="Adjunto de notificación" style="max-width: 100%; max-height: 380px; border-radius: 6px; border: 1px solid #e2e8f0; object-fit: contain;" />
        </div>
        """

    # Formatear saltos de línea en el mensaje
    mensaje_html = "<br>".join(escape(mensaje).splitlines())

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(titulo)} - SIRAE PAE</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f0f4f8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #2d3748; line-height: 1.6;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f0f4f8; padding: 24px 12px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); border: 1px solid #e2e8f0;">
                    <!-- Cabecera Institucional -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 100%); padding: 24px 28px; text-align: left; color: #ffffff;">
                            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; opacity: 0.85; margin-bottom: 4px; font-weight: 600;">
                                Sistema de Información y Registro de Alimentación Escolar
                            </div>
                            <h1 style="margin: 0; font-size: 22px; font-weight: 700; color: #ffffff;">
                                SIRAE PAE
                            </h1>
                        </td>
                    </tr>

                    <!-- Etiqueta de Categoría -->
                    <tr>
                        <td style="padding: 20px 28px 0 28px;">
                            <span style="display: inline-block; padding: 4px 10px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; border-radius: 12px; background-color: #ebf8ff; color: #2b6cb0;">
                                {escape(categoria)}
                            </span>
                            <h2 style="margin: 12px 0 6px 0; font-size: 19px; color: #1a202c; font-weight: 700;">
                                {escape(titulo)}
                            </h2>
                        </td>
                    </tr>

                    <!-- Contenido Central -->
                    <tr>
                        <td style="padding: 12px 28px 24px 28px; font-size: 15px; color: #2d3748;">
                            {seccion_remitente}

                            <div style="margin-top: 14px; font-size: 15px; line-height: 1.65; color: #2d3748;">
                                {mensaje_html}
                            </div>

                            {seccion_imagen}

                            <!-- Botón de Acción -->
                            <div style="margin-top: 28px; text-align: center;">
                                <a href="{enlace_final}" target="_blank" style="display: inline-block; padding: 12px 24px; background-color: #2b6cb0; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px; box-shadow: 0 2px 4px rgba(43, 108, 176, 0.3);">
                                    {escape(texto_accion)}
                                </a>
                            </div>
                        </td>
                    </tr>

                    <!-- Pie de Página Institucional -->
                    <tr>
                        <td style="background-color: #edf2f7; padding: 18px 28px; text-align: center; font-size: 12px; color: #718096; border-top: 1px solid #e2e8f0;">
                            <p style="margin: 0 0 6px 0;">
                                Este mensaje fue enviado automáticamente por el sistema <strong>SIRAE PAE</strong>.
                            </p>
                            <p style="margin: 0; font-size: 11px; color: #a0aec0;">
                                Por favor no respondas a este correo. Para gestionar notificaciones, accede a la plataforma web.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def enviar_correo_notificacion(
    asunto: str,
    destinatarios: Sequence[str] | str,
    mensaje_texto: str,
    mensaje_html: str | None = None,
    remitente: str | None = None,
) -> dict:
    """
    Envía un correo electrónico vía SMTP con soporte HTML y texto plano.
    Diseñado con tolerancia a fallos: captura errores de conexión, autenticación
    o timeout para no interrumpir el flujo principal del backend.
    """
    if isinstance(destinatarios, str):
        lista_destinatarios = [destinatarios.strip()]
    else:
        lista_destinatarios = [
            d.strip() for d in destinatarios if d and str(d).strip()
        ]

    if not lista_destinatarios:
        logger.warning(
            "Intento de envío de correo cancelado: no se indicaron destinatarios válidos."
        )
        return {
            "exito": False,
            "enviados": [],
            "fallidos": [],
            "error": "No hay destinatarios válidos.",
        }

    from_email = remitente or getattr(
        settings, "DEFAULT_FROM_EMAIL", "SIRAE PAE <no-reply@sirae-pae.edu.co>"
    )

    # Validar presencia mínima de credenciales cuando se use SMTP
    backend = getattr(settings, "EMAIL_BACKEND", "")
    es_smtp = "smtp.EmailBackend" in backend
    host_user = getattr(settings, "EMAIL_HOST_USER", "")
    host_pwd = getattr(settings, "EMAIL_HOST_PASSWORD", "")

    if es_smtp and (not host_user or not host_pwd):
        msg_aviso = (
            "No se puede despachar correo vía SMTP: EMAIL_HOST_USER o "
            "EMAIL_HOST_PASSWORD no están configurados en las variables de entorno."
        )
        logger.warning(msg_aviso)
        return {
            "exito": False,
            "enviados": [],
            "fallidos": lista_destinatarios,
            "error": msg_aviso,
        }

    asunto_limpio = asunto.strip().replace("\n", " ").replace("\r", " ")
    enviados: list[str] = []
    fallidos: list[str] = []
    ultimo_error: str | None = None

    for destino in lista_destinatarios:
        try:
            send_mail(
                subject=asunto_limpio,
                message=mensaje_texto,
                from_email=from_email,
                recipient_list=[destino],
                html_message=mensaje_html,
                fail_silently=False,
            )
            enviados.append(destino)
            logger.info(
                "Correo SMTP enviado exitosamente a: %s - Asunto: '%s'",
                destino,
                asunto_limpio,
            )

        except smtplib.SMTPAuthenticationError as exc:
            ultimo_error = (
                f"Fallo de autenticación con Google SMTP (código 535): {exc}. "
                "Verifique que EMAIL_HOST_USER sea correcto y que EMAIL_HOST_PASSWORD "
                "sea una 'Contraseña de aplicación' de Google de 16 caracteres."
            )
            logger.error("Error SMTP para %s: %s", destino, ultimo_error)
            fallidos.append(destino)

        except (socket.timeout, TimeoutError) as exc:
            ultimo_error = (
                f"Tiempo de espera agotado (timeout) conectando con SMTP ({settings.EMAIL_HOST}:{settings.EMAIL_PORT}): {exc}"
            )
            logger.error("Timeout SMTP para %s: %s", destino, ultimo_error)
            fallidos.append(destino)

        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected) as exc:
            ultimo_error = f"Error de conexión con el servidor SMTP: {exc}"
            logger.error("Fallo de conexión SMTP para %s: %s", destino, ultimo_error)
            fallidos.append(destino)

        except smtplib.SMTPException as exc:
            ultimo_error = f"Excepción general SMTP al enviar a {destino}: {exc}"
            logger.error(ultimo_error)
            fallidos.append(destino)

        except (OSError, ConnectionError) as exc:
            ultimo_error = f"Error de red o conexión al servidor SMTP: {exc}"
            logger.error(ultimo_error)
            fallidos.append(destino)

        except Exception as exc:
            ultimo_error = f"Error inesperado al enviar correo a {destino}: {exc}"
            logger.exception(ultimo_error)
            fallidos.append(destino)

    exito = len(enviados) > 0 and len(fallidos) == 0
    return {
        "exito": exito,
        "parcial": len(enviados) > 0 and len(fallidos) > 0,
        "enviados": enviados,
        "fallidos": fallidos,
        "error": ultimo_error,
    }


# Alias de utilidad para compatibilidad de importaciones
enviar_correo = enviar_correo_notificacion


def notificar_usuarios_por_correo(
    destinatarios: Iterable,
    remitente,
    titulo: str,
    mensaje: str,
    imagen_url: str | None = None,
    categoria: str = "NOTIFICACIÓN SIRAE",
) -> dict:
    """
    Envía notificaciones por correo electrónico a una lista de usuarios (o correos).
    Nunca lanza excepciones no controladas hacia el llamador.
    """
    try:
        correos_destinatarios: list[str] = []
        for dest in destinatarios:
            if hasattr(dest, "correo") and getattr(dest, "correo", None):
                correos_destinatarios.append(dest.correo)
            elif isinstance(dest, str) and "@" in dest:
                correos_destinatarios.append(dest)

        if not correos_destinatarios:
            logger.info("No hay correos destinatarios válidos para la notificación.")
            return {
                "exito": False,
                "enviados": [],
                "fallidos": [],
                "error": "Sin destinatarios con correo.",
            }

        remitente_nombre = ""
        remitente_rol = ""
        if hasattr(remitente, "nombre_completo"):
            remitente_nombre = remitente.nombre_completo
            if hasattr(remitente, "rol") and remitente.rol:
                remitente_rol = str(remitente.rol.nombre)
        elif isinstance(remitente, str):
            remitente_nombre = remitente

        asunto = f"[SIRAE PAE] {titulo}"

        # Cuerpo en texto plano legible
        mensaje_texto = (
            f"SIRAE PAE - {categoria}\n"
            f"{'=' * 45}\n"
            f"Asunto: {titulo}\n"
        )
        if remitente_nombre:
            rol_str = f" ({remitente_rol})" if remitente_rol else ""
            mensaje_texto += f"De: {remitente_nombre}{rol_str}\n"
        mensaje_texto += (
            f"{'=' * 45}\n\n"
            f"{mensaje}\n\n"
        )
        if imagen_url:
            mensaje_texto += f"Imagen adjunta: {imagen_url}\n\n"
        mensaje_texto += (
            "Para gestionar esta notificación, ingresa a la plataforma web de SIRAE PAE.\n"
            "Este es un mensaje institucional automático. Por favor no responder."
        )

        # Cuerpo HTML enriquecido
        mensaje_html = construir_plantilla_notificacion_html(
            titulo=titulo,
            mensaje=mensaje,
            remitente_nombre=remitente_nombre,
            remitente_rol=remitente_rol,
            imagen_url=imagen_url,
            categoria=categoria,
        )

        return enviar_correo_notificacion(
            asunto=asunto,
            destinatarios=correos_destinatarios,
            mensaje_texto=mensaje_texto,
            mensaje_html=mensaje_html,
        )
    except Exception as exc:
        logger.exception(
            "Excepción no esperada en notificar_usuarios_por_correo: %s", exc
        )
        return {
            "exito": False,
            "enviados": [],
            "fallidos": [],
            "error": str(exc),
        }


def enviar_alerta_stock_inventario(
    ingrediente_nombre: str,
    sede_nombre: str,
    stock_actual,
    stock_minimo,
    unidad_medida: str = "",
    destinatarios: Sequence[str] | None = None,
    id_remitente: int | None = None,
) -> dict:
    """
    Construye y despacha una alerta crítica de inventario (stock bajo o agotado)
    creando la Notificación en la base de datos y notificando a los supervisores/administradores vía correo.
    """
    from apps_sirae.notificaciones.models import Notificacion
    from apps_sirae.usuarios.models import Usuario

    titulo = f"ALERTA: Stock bajo en {ingrediente_nombre} ({sede_nombre})"
    unidad_str = f" {unidad_medida}" if unidad_medida else ""
    cuerpo_alerta = (
        f"Se ha detectado nivel crítico en el inventario de la sede '{sede_nombre}'.\n\n"
        f"• Producto: {ingrediente_nombre}\n"
        f"• Stock Actual: {stock_actual}{unidad_str}\n"
        f"• Stock Mínimo Requerido: {stock_minimo}{unidad_str}\n\n"
        "Se recomienda coordinar inmediatamente el abastecimiento o la asignación de inventario."
    )

    # Identificar destinatarios si no se pasan explícitamente
    usuarios_destino = []
    if destinatarios is None:
        usuarios_destino = list(
            Usuario.objects.filter(
                is_active=True,
                rol__nombre__in=["Administrador", "supervisor", "JefaManipuladoras"],
            ).select_related("rol")
        )
    else:
        usuarios_destino = list(
            Usuario.objects.filter(correo__in=destinatarios, is_active=True).select_related(
                "rol"
            )
        )

    # Registrar en base de datos de manera atómica
    if usuarios_destino:
        Notificacion.objects.bulk_create([
            Notificacion(
                id_usuario=u.id_usuario,
                id_remitente=id_remitente,
                titulo=titulo,
                mensaje=cuerpo_alerta,
            )
            for u in usuarios_destino
        ])

    # Enviar correo electrónico seguro
    return notificar_usuarios_por_correo(
        destinatarios=usuarios_destino if usuarios_destino else (destinatarios or []),
        remitente="Sistema Central de Inventario SIRAE",
        titulo=titulo,
        mensaje=cuerpo_alerta,
        categoria="ALERTA DE INVENTARIO",
    )
