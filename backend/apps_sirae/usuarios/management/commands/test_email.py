from django.conf import settings
from django.core.management.base import BaseCommand

from apps_sirae.usuarios.api.password_reset import enviar_email_brevo_api


class Command(BaseCommand):
    help = (
        "Prueba la configuración y el envío real de correos electrónicos vía "
        "Gmail SMTP o Brevo HTTP API."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "email_destino",
            type=str,
            help="Correo electrónico real donde quieres recibir el mensaje de prueba",
        )

    def handle(self, *args, **options):
        email_destino = options["email_destino"].strip()

        self.stdout.write(self.style.NOTICE("=" * 65))
        self.stdout.write(
            self.style.NOTICE(" DIAGNOSTICO DE CONFIGURACION DE CORREO - SIRAE PAE")
        )
        self.stdout.write(self.style.NOTICE("=" * 65))

        brevo_key = str(getattr(settings, "BREVO_API_KEY", "") or "").strip()
        transporte = (
            "Brevo HTTP API"
            if brevo_key
            else f"SMTP ({getattr(settings, 'EMAIL_HOST', '')}:{getattr(settings, 'EMAIL_PORT', '')})"
        )

        pwd = str(getattr(settings, "EMAIL_HOST_PASSWORD", "") or "")
        masked_pwd = (
            (pwd[:2] + "*" * (len(pwd) - 4) + pwd[-2:])
            if len(pwd) > 4
            else ("****" if pwd else "(No configurada)")
        )

        self.stdout.write(f" - TRANSPORTE ACTIVO: {transporte}")
        self.stdout.write(
            f" - BREVO_API_KEY    : {'Configurada' if brevo_key else '(No configurada - usará SMTP)'}"
        )
        self.stdout.write(f" - EMAIL_BACKEND    : {getattr(settings, 'EMAIL_BACKEND', '')}")
        self.stdout.write(f" - EMAIL_HOST       : {getattr(settings, 'EMAIL_HOST', '')}")
        self.stdout.write(f" - EMAIL_PORT       : {getattr(settings, 'EMAIL_PORT', '')}")
        self.stdout.write(f" - EMAIL_USE_TLS    : {getattr(settings, 'EMAIL_USE_TLS', '')}")
        self.stdout.write(f" - EMAIL_USE_SSL    : {getattr(settings, 'EMAIL_USE_SSL', '')}")
        self.stdout.write(
            f" - EMAIL_HOST_USER  : {getattr(settings, 'EMAIL_HOST_USER', '') or '(Vacio)'}"
        )
        self.stdout.write(f" - EMAIL_PASSWORD   : {masked_pwd}")
        self.stdout.write(f" - DEFAULT_FROM     : {getattr(settings, 'DEFAULT_FROM_EMAIL', '')}")
        self.stdout.write(
            f" - EMAIL_TIMEOUT    : {getattr(settings, 'EMAIL_TIMEOUT', 15)} segundos"
        )
        self.stdout.write(self.style.NOTICE("-" * 65))
        self.stdout.write(f"Intentando enviar correo de prueba a: {email_destino} ...\n")

        backend = getattr(settings, "EMAIL_BACKEND", "")
        if "console.EmailBackend" in backend and not brevo_key:
            self.stdout.write(
                self.style.WARNING(
                    "[AVISO] EMAIL_BACKEND está configurado como 'console.EmailBackend'.\n"
                    "        El correo NO saldrá a internet; solo se imprimirá en la consola.\n"
                )
            )

        asunto = f"Prueba Exitosa de Envío de Correo - SIRAE PAE ({transporte})"
        mensaje_texto = (
            "Hola,\n\n"
            "Este es un correo de prueba generado desde el backend de SIRAE.\n"
            f"Transporte utilizado: {transporte}.\n\n"
            "Si estás leyendo este mensaje en tu bandeja de entrada, la recuperación "
            "de contraseña funcionará correctamente.\n\n"
            "Equipo SIRAE PAE."
        )
        mensaje_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 550px; margin: 0 auto; border: 1px solid #cbd5e0; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #2b6cb0; color: white; padding: 20px; text-align: center;">
                <h2 style="margin: 0;">SIRAE - Sistema 1-2-3 del PAE</h2>
                <p style="margin: 5px 0 0 0; font-size: 14px;">Prueba de Envío de Correo ({transporte})</p>
            </div>
            <div style="padding: 25px; background-color: #ffffff; color: #2d3748;">
                <h3 style="color: #38a169; margin-top: 0;">Conexión exitosa</h3>
                <p>Si estás leyendo este correo, la configuración de envío mediante <strong>{transporte}</strong> funciona correctamente.</p>
                <p>Los correos de recuperación de contraseña llegarán a la bandeja de entrada de los usuarios.</p>
            </div>
        </div>
        """

        try:
            enviar_email_brevo_api(
                destinatario_email=email_destino,
                asunto=asunto,
                mensaje_texto=mensaje_texto,
                mensaje_html=mensaje_html,
            )
            self.stdout.write(self.style.SUCCESS("=" * 65))
            self.stdout.write(
                self.style.SUCCESS(
                    f"[OK] Correo de prueba enviado correctamente vía {transporte}."
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Revisa la bandeja de entrada (y Spam) de: {email_destino}"
                )
            )
            self.stdout.write(self.style.SUCCESS("=" * 65))
        except Exception as exc:
            self.stdout.write(self.style.ERROR("=" * 65))
            self.stdout.write(self.style.ERROR("[ERROR] AL ENVIAR EL CORREO:"))
            self.stdout.write(self.style.ERROR(f"   {exc}"))
            self.stdout.write(self.style.ERROR("=" * 65))
            self.stdout.write(self.style.WARNING("\nPosibles causas:"))
            self.stdout.write(
                " 1. Gmail SMTP: verifica EMAIL_HOST_USER y usa una Contraseña de Aplicación de 16 caracteres (con 2FA activo)."
            )
            self.stdout.write(
                " 2. Gmail SMTP: verifica EMAIL_HOST=smtp.gmail.com, EMAIL_PORT=587 y EMAIL_USE_TLS=True."
            )
            self.stdout.write(
                " 3. Brevo (opcional): si usas BREVO_API_KEY, verifica que la clave y el remitente estén activos.\n"
            )
