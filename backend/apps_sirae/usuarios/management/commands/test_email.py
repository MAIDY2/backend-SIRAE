import os
from django.core.management.base import BaseCommand
from django.conf import settings
from apps_sirae.usuarios.api.password_reset import enviar_email_brevo_api


class Command(BaseCommand):
    help = 'Prueba la configuracion y el envio real de correos electronicos via Brevo HTTP API o SMTP (Render / Produccion)'

    def add_arguments(self, parser):
        parser.add_argument('email_destino', type=str, help='Correo electronico real donde quieres recibir el mensaje de prueba')

    def handle(self, *args, **options):
        email_destino = options['email_destino']

        self.stdout.write(self.style.NOTICE("=" * 65))
        self.stdout.write(self.style.NOTICE(" DIAGNOSTICO DE CONFIGURACION DE CORREO - SIRAE PAE"))
        self.stdout.write(self.style.NOTICE("=" * 65))

        brevo_key = os.getenv("BREVO_API_KEY", "").strip() or getattr(settings, "BREVO_API_KEY", "").strip()
        masked_brevo = (brevo_key[:6] + "..." + brevo_key[-4:]) if len(brevo_key) > 10 else ("Configurada" if brevo_key else "(No configurada)")

        pwd = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        masked_pwd = (pwd[:2] + '*' * (len(pwd) - 4) + pwd[-2:]) if len(pwd) > 4 else ('****' if pwd else '(No configurada)')

        self.stdout.write(f" - BREVO_API_KEY    : {masked_brevo}")
        self.stdout.write(f" - BACKEND_URL      : {getattr(settings, 'BACKEND_URL', 'https://backend-sirae-pyim.onrender.com')}")
        self.stdout.write(f" - EMAIL_BACKEND    : {getattr(settings, 'EMAIL_BACKEND', '')}")
        self.stdout.write(f" - EMAIL_HOST       : {getattr(settings, 'EMAIL_HOST', '')}")
        self.stdout.write(f" - EMAIL_PORT       : {getattr(settings, 'EMAIL_PORT', '')}")
        self.stdout.write(f" - EMAIL_USE_TLS    : {getattr(settings, 'EMAIL_USE_TLS', '')}")
        self.stdout.write(f" - EMAIL_HOST_USER  : {getattr(settings, 'EMAIL_HOST_USER', '') or '(Vacio)'}")
        self.stdout.write(f" - EMAIL_PASSWORD   : {masked_pwd}")
        self.stdout.write(f" - DEFAULT_FROM     : {getattr(settings, 'DEFAULT_FROM_EMAIL', '')}")
        self.stdout.write(f" - EMAIL_TIMEOUT    : {getattr(settings, 'EMAIL_TIMEOUT', 10)} segundos")
        self.stdout.write(self.style.NOTICE("-" * 65))
        self.stdout.write(f"Intentando enviar correo de prueba a: {email_destino} ...\n")

        backend = getattr(settings, 'EMAIL_BACKEND', '')
        if 'console.EmailBackend' in backend and not brevo_key:
            self.stdout.write(
                self.style.WARNING(
                    "[AVISO] EMAIL_BACKEND esta configurado como 'console.EmailBackend' y no hay BREVO_API_KEY.\n"
                    "        El correo NO saldra a internet; solo se imprimira en la consola.\n"
                )
            )

        asunto = "Prueba Exitosa de Envio de Correo - SIRAE PAE"
        mensaje_texto = (
            "Hola,\n\n"
            "Este es un correo de prueba generado desde el backend de SIRAE (Sistema de Alimentacion Escolar).\n"
            "Si estas leyendo este mensaje en tu bandeja de entrada, significa que la conexion con Brevo HTTP API / SMTP "
            "en tu servidor de Render (https://backend-sirae-pyim.onrender.com) funciona a la perfeccion.\n\n"
            "Estado: Verificado con exito.\n"
            "Equipo SIRAE PAE."
        )

        mensaje_html = """
        <div style="font-family: Arial, sans-serif; max-width: 550px; margin: 0 auto; border: 1px solid #cbd5e0; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #2b6cb0; color: white; padding: 20px; text-align: center;">
                <h2 style="margin: 0;">SIRAE - Sistema 1-2-3 del PAE</h2>
                <p style="margin: 5px 0 0 0; font-size: 14px;">Prueba de Envio de Correo</p>
            </div>
            <div style="padding: 25px; background-color: #ffffff; color: #2d3748;">
                <h3 style="color: #38a169; margin-top: 0;">Conexion exitosa</h3>
                <p>Si estas leyendo este correo, la configuracion de envio en tu servidor (Render) esta funcionando perfectamente mediante la API HTTP de Brevo.</p>
                <p>A partir de ahora, cuando un usuario solicite recuperacion de contrasena en SIRAE, recibira el correo con su enlace y token en su bandeja de entrada real sin sufrir bloqueos SMTP.</p>
                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
                <p style="font-size: 12px; color: #718096; margin-bottom: 0;">
                    Mensaje generado automaticamente por el comando test_email de SIRAE PAE (https://backend-sirae-pyim.onrender.com).
                </p>
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
            self.stdout.write(self.style.SUCCESS("[OK] El correo de prueba fue enviado correctamente."))
            self.stdout.write(self.style.SUCCESS(f"Revisa la bandeja de entrada (y la carpeta Spam) de: {email_destino}"))
            self.stdout.write(self.style.SUCCESS("=" * 65))

        except Exception as e:
            self.stdout.write(self.style.ERROR("=" * 65))
            self.stdout.write(self.style.ERROR("[ERROR] AL ENVIAR EL CORREO:"))
            self.stdout.write(self.style.ERROR(f"   {str(e)}"))
            self.stdout.write(self.style.ERROR("=" * 65))
            self.stdout.write(self.style.WARNING("\nPosibles causas:"))
            self.stdout.write(" 1. Brevo: Verifica que BREVO_API_KEY este correctamente configurada en Render.")
            self.stdout.write(" 2. Brevo: Asegurate de que el remitente (DEFAULT_FROM_EMAIL) este verificado como Sender en tu panel de Brevo.")
            self.stdout.write(" 3. Brevo: Revisa que tu cuenta de Brevo no este suspendida o sin creditos diarios.\n")
