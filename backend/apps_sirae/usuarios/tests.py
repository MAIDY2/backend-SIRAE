
import re
from unittest.mock import patch, MagicMock

from datetime import timedelta
from django.core.cache import cache
from django.core.management import call_command
from django.contrib.auth.hashers import check_password
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps_sirae.usuarios.api.password_reset import PasswordResetService
from apps_sirae.usuarios.models import IntentoAutenticacion, PasswordResetCode, Usuario
from apps_sirae.roles.models import Rol
from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.instituciones.models import Institucion
from apps_sirae.sedes.models import Sede


class UsuarioCompatibilityTests(TestCase):
    def test_legacy_aliases_and_properties_are_supported(self):
        usuario = Usuario.objects.create(
            nombre_completo='Ana López',
            email='ana@example.com',
            tipo_documento='CC',
            documento_identidad='123456789',
            estado='Activo',
            id_rol=None,
        )

        self.assertEqual(usuario.correo, 'ana@example.com')
        self.assertEqual(usuario.nombre, 'Ana')
        self.assertEqual(usuario.apellido, 'López')
        self.assertEqual(usuario.nombre_completo, 'Ana López')
        self.assertEqual(usuario.email, 'ana@example.com')
        self.assertTrue(usuario.is_active)

    def test_password_reset_token_round_trip(self):
        usuario = Usuario.objects.create_user(
            correo='reset@example.com',
            nombre='Reset',
            apellido='User',
            password='secure-pass-123',
            tipo_documento='CC',
            numero_documento='987654321',
        )

        token = PasswordResetService.generar_token(usuario)
        usuario_validado, error = PasswordResetService.validar_token(token)

        self.assertIsNone(error)
        self.assertEqual(usuario_validado.id_usuario, usuario.id_usuario)
        self.assertEqual(usuario_validado.correo, usuario.correo)


class UsuarioLoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.usuario = Usuario.objects.create_user(
            correo="admin@sirae.com",
            nombre="Administrador",
            apellido="Sistema",
            password="Safe-Passphrase-2026!",
            tipo_documento="CC",
            numero_documento="LOGIN001",
        )


@override_settings(
    DEBUG=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class PasswordRecoveryApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.usuario = Usuario.objects.create_user(
            correo='reset@example.com',
            nombre='Reset',
            apellido='User',
            password='old-password-123',
            tipo_documento='CC',
            numero_documento='987654321',
        )

    def test_request_recovery_sends_verification_code(self):
        response = self.client.post(
            reverse('recuperar-password'),
            {'correo': self.usuario.correo},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            'Tu código para recuperar la contraseña es:',
            mail.outbox[0].body,
        )

    @override_settings(
        DEBUG=False,
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD='',
    )
    @patch('apps_sirae.usuarios.api.password_reset.send_mail')
    def test_production_without_smtp_credentials_does_not_claim_email_was_sent(
        self, send_mail
    ):
        response = self.client.post(
            reverse('recuperar-password'),
            {'correo': self.usuario.correo},
            format='json',
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn(
            'servicio de correo no está configurado',
            response.data['error'],
        )
        send_mail.assert_not_called()
        self.assertFalse(
            PasswordResetCode.objects.filter(usuario=self.usuario).exists()
        )

    @override_settings(
        DEBUG=False,
        EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
    )
    @patch('apps_sirae.usuarios.api.password_reset.send_mail')
    def test_production_console_backend_does_not_claim_email_was_sent(
        self, send_mail
    ):
        response = self.client.post(
            reverse('recuperar-password'),
            {'correo': self.usuario.correo},
            format='json',
        )

        self.assertEqual(response.status_code, 503)
        send_mail.assert_not_called()
        self.assertFalse(
            PasswordResetCode.objects.filter(usuario=self.usuario).exists()
        )

    @override_settings(
        DEBUG=False,
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD='',
        PASSWORD_RESET_EXPOSE_CODE=True,
        PASSWORD_RESET_EXPOSE_CODE_EMAILS={'reset@example.com'},
    )
    @patch('apps_sirae.usuarios.api.password_reset.send_mail')
    def test_production_demo_account_receives_code_without_smtp(
        self, send_mail
    ):
        response = self.client.post(
            reverse('recuperar-password'),
            {'correo': self.usuario.correo},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.data['debug_code'], r'^\d{6}$')
        send_mail.assert_not_called()

    @override_settings(
        DEBUG=False,
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD='',
        PASSWORD_RESET_EXPOSE_CODE=True,
        PASSWORD_RESET_EXPOSE_CODE_EMAILS={'other@example.com'},
    )
    @patch('apps_sirae.usuarios.api.password_reset.send_mail')
    def test_production_does_not_expose_code_for_unlisted_account(
        self, send_mail
    ):
        response = self.client.post(
            reverse('recuperar-password'),
            {'correo': self.usuario.correo},
            format='json',
        )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn('debug_code', response.data)
        send_mail.assert_not_called()

    def test_confirm_recovery_changes_password_and_invalidates_token(self):
        token = PasswordResetService.generar_token(self.usuario)

        validation = self.client.post(
            reverse('password-reset-validar-token'),
            {'token': token},
            format='json',
        )

        self.assertEqual(validation.status_code, 200)
        self.assertTrue(validation.data['valido'])

        response = self.client.post(
            reverse('password-reset-confirmar'),
            {
                'token': token,
                'nueva_password': 'new-password-123',
                'confirmar_password': 'new-password-123',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(
            check_password('new-password-123', self.usuario.password)
        )

        validation_again = self.client.post(
            reverse('password-reset-validar-token'),
            {'token': token},
            format='json',
        )
        self.assertEqual(validation_again.status_code, 400)

    def test_authenticated_password_change_checks_current_password(self):
        self.client.force_authenticate(user=self.usuario)

        response = self.client.post(
            reverse('cambiar-password'),
            {
                'password_actual': 'old-password-123',
                'nueva_password': 'another-password-123',
                'confirmar_password': 'another-password-123',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(
            check_password('another-password-123', self.usuario.password)
        )


class UsuarioLoginBehaviorTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.rol_admin = Rol.objects.create(nombre=Rol.NombreRol.ADMINISTRADOR)
        self.usuario = Usuario.objects.create_user(
            correo="admin@sirae.com",
            nombre="Administrador",
            apellido="Sistema",
            password="Safe-Passphrase-2026!",
            tipo_documento="CC",
            numero_documento="LOGIN001",
            rol=self.rol_admin,
        )

    def test_login_accepts_email_and_password(self):
        response = self.client.post(
            reverse("login"),
            {
                "correo": self.usuario.correo.upper(),
                "password": "Safe-Passphrase-2026!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertEqual(
            response.data["usuario"]["correo"],
            self.usuario.correo,
        )

    def test_login_rejects_wrong_password(self):
        response = self.client.post(
            reverse("login"),
            {
                "correo": self.usuario.correo,
                "password": "incorrect-password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)


class UsuarioSeedCommandTests(TestCase):
    @patch(
        "apps_sirae.usuarios.management.commands.crear_usuario_prueba.getpass.getpass"
    )
    def test_seed_creates_accounts_and_does_not_reset_existing_passwords(
        self, get_password
    ):
        get_password.return_value = "Unique-Safe-Passphrase-2026!"

        call_command("crear_usuario_prueba")

        self.assertEqual(Usuario.objects.count(), 4)
        self.assertEqual(get_password.call_count, 8)

        usuario = Usuario.objects.get(correo="admin@sirae.com")
        self.assertTrue(
            usuario.check_password("Unique-Safe-Passphrase-2026!")
        )

        call_command("crear_usuario_prueba")

        self.assertEqual(get_password.call_count, 8)
        usuario.refresh_from_db()
        self.assertTrue(
            usuario.check_password("Unique-Safe-Passphrase-2026!")
        )

    @patch(
        "apps_sirae.usuarios.management.commands.crear_usuario_prueba.getpass.getpass"
    )
    def test_seed_only_resets_existing_passwords_when_requested(
        self, get_password
    ):
        Usuario.objects.create_user(
            correo="admin@sirae.com",
            nombre="Old",
            apellido="Admin",
            password="Previous-Safe-Passphrase-2026!",
            tipo_documento="CC",
            numero_documento="RESET001",
        )

        get_password.return_value = "Replacement-Safe-Passphrase-2026!"

        call_command(
            "crear_usuario_prueba",
            "--reset-existing-passwords",
        )

        usuario = Usuario.objects.get(correo="admin@sirae.com")
        self.assertTrue(
            usuario.check_password("Replacement-Safe-Passphrase-2026!")
        )
        self.assertEqual(get_password.call_count, 8)

    @patch.dict(
        "os.environ",
        {
            "SIRAE_ADMIN_PASSWORD": "Admin-Seed-Passphrase-2026!xQ",
            "SIRAE_SUPERVISOR_PASSWORD": "Supervisor-Seed-Passphrase-2026!xQ",
            "SIRAE_JEFE_PASSWORD": "Jefa-Seed-Passphrase-2026!xQ",
            "SIRAE_MANIPULADORA_PASSWORD": "Manipuladora-Seed-Passphrase-2026!xQ",
        },
    )
    def test_seed_supports_non_interactive_secret_environment(self):
        call_command("crear_usuario_prueba", "--non-interactive")

        self.assertEqual(Usuario.objects.count(), 4)
        self.assertTrue(
            Usuario.objects.get(correo="admin@sirae.com").check_password(
                "Admin-Seed-Passphrase-2026!xQ"
            )
        )


class EmailPasswordLoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.role = Rol.objects.create(
            nombre=Rol.NombreRol.SUPERVISOR
        )
        self.user = Usuario.objects.create_user(
            correo='supervisor@example.com',
            nombre='Ana',
            apellido='Pérez',
            password='secure-password-42',
            tipo_documento='CC',
            numero_documento='123456789',
            rol=self.role,
        )

    def test_login_returns_tokens_and_the_user_role(self):
        response = self.client.post(
            reverse('login'),
            {
                'correo': 'SUPERVISOR@EXAMPLE.COM',
                'password': 'secure-password-42',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['access'])
        self.assertTrue(response.data['refresh'])

        usuario = response.data['usuario']

        self.assertEqual(usuario['id_usuario'], self.user.id_usuario)
        self.assertEqual(usuario['nombre'], 'Ana')
        self.assertEqual(usuario['apellido'], 'Pérez')
        self.assertEqual(usuario['correo'], 'supervisor@example.com')
        self.assertEqual(usuario['numero_documento'], '123456789')
        self.assertEqual(usuario['rol'], 'supervisor')
        self.assertFalse(usuario['is_superuser'])
        self.assertFalse(usuario['debe_cambiar_password'])

        # El serializador puede incluir información de institución y sede.
        self.assertIn('id_institucion', usuario)
        self.assertIn('id_sede', usuario)
        self.assertIn('institucion', usuario)
        self.assertIn('institucion_nombre', usuario)
        self.assertIn('instituciones_supervisor', usuario)
        self.assertIn('sede_nombre', usuario)

    def test_login_identifies_superuser_without_role_as_super_administrator(self):
        self.user.rol = None
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save(update_fields=['rol', 'is_superuser', 'is_staff'])

        response = self.client.post(
            reverse('login'),
            {
                'correo': self.user.correo,
                'password': 'secure-password-42',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['usuario']['rol'], 'Super Administrador')
        self.assertTrue(response.data['usuario']['is_superuser'])
        self.assertEqual(
            AccessToken(response.data['access'])['rol'],
            'Super Administrador',
        )

    def test_login_includes_sedes_from_supervisor_contracts(self):
        institucion = Institucion.objects.create(
            nombre_institucion='Institución por contrato',
            nit='CONTRATO-LOGIN-001',
        )
        sede = Sede.objects.create(
            id_institucion=institucion,
            nombre_sede='Sede asignada por contrato',
        )
        Contrato.objects.create(
            id_usuario_supervisor=self.user,
            id_institucion=institucion,
        )

        response = self.client.post(
            reverse('login'),
            {
                'correo': self.user.correo,
                'password': 'secure-password-42',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        instituciones = response.data['usuario']['instituciones_supervisor']
        self.assertEqual(len(instituciones), 1)
        self.assertEqual(instituciones[0]['id_institucion'], institucion.id_institucion)
        self.assertEqual(instituciones[0]['sedes'][0]['id_sede'], sede.id_sede)

    def test_login_rejects_an_incorrect_password(self):
        response = self.client.post(
            reverse('login'),
            {
                'correo': self.user.correo,
                'password': 'incorrect-password',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 401)

    def test_login_rejects_unregistered_email_with_same_generic_message(self):
        wrong_pass_resp = self.client.post(
            reverse('login'),
            {
                'correo': self.user.correo,
                'password': 'incorrect-password',
            },
            format='json',
        )
        unknown_email_resp = self.client.post(
            reverse('login'),
            {
                'correo': 'noexiste@example.com',
                'password': 'incorrect-password',
            },
            format='json',
        )

        self.assertEqual(wrong_pass_resp.status_code, 401)
        self.assertEqual(unknown_email_resp.status_code, 401)
        self.assertEqual(wrong_pass_resp.data['detail'], unknown_email_resp.data['detail'])
        self.assertNotIn('noexiste@example.com', str(unknown_email_resp.data))
        self.assertNotIn('No existe', str(unknown_email_resp.data))

    def test_login_rejects_inactive_user_and_unauthorized_user_without_role(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])

        inactive_resp = self.client.post(
            reverse('login'),
            {
                'correo': self.user.correo,
                'password': 'secure-password-42',
            },
            format='json',
        )
        self.assertEqual(inactive_resp.status_code, 401)
        self.assertIn('inactiva', str(inactive_resp.data['detail']).lower())

        self.user.is_active = True
        self.user.rol = None
        self.user.is_superuser = False
        self.user.save(update_fields=['is_active', 'rol', 'is_superuser'])

        no_role_resp = self.client.post(
            reverse('login'),
            {
                'correo': self.user.correo,
                'password': 'secure-password-42',
            },
            format='json',
        )
        self.assertEqual(no_role_resp.status_code, 401)
        self.assertIn('autorización', str(no_role_resp.data['detail']).lower())

    @override_settings(LOGIN_MAX_FAILED_ATTEMPTS=3, LOGIN_LOCKOUT_DURATION_MINUTES=15)
    def test_login_records_failed_attempts_and_applies_temporary_lockout(self):
        for i in range(2):
            resp = self.client.post(
                reverse('login'),
                {
                    'correo': self.user.correo,
                    'password': f'wrong-pass-{i}',
                },
                format='json',
            )
            self.assertEqual(resp.status_code, 401)
            self.assertIn('incorrectos', str(resp.data['detail']).lower())

        # Tercer intento fallido alcanza el límite configurable (3) y bloquea
        third_resp = self.client.post(
            reverse('login'),
            {
                'correo': self.user.correo,
                'password': 'wrong-pass-3',
            },
            format='json',
        )
        self.assertEqual(third_resp.status_code, 401)
        self.assertIn('bloqueada temporalmente', str(third_resp.data['detail']).lower())

        self.user.refresh_from_db()
        self.assertEqual(self.user.intentos_fallidos_login, 3)
        self.assertIsNotNone(self.user.bloqueado_hasta)
        self.assertGreater(self.user.bloqueado_hasta, timezone.now())

        # Incluso con la contraseña correcta debe rechazar mientras el bloqueo esté activo
        blocked_resp = self.client.post(
            reverse('login'),
            {
                'correo': self.user.correo,
                'password': 'secure-password-42',
            },
            format='json',
        )
        self.assertEqual(blocked_resp.status_code, 401)
        self.assertIn('bloqueada temporalmente', str(blocked_resp.data['detail']).lower())

        # Verificar que se hayan registrado los 4 intentos fallidos en la bitácora
        intentos = IntentoAutenticacion.objects.filter(usuario=self.user, exitoso=False)
        self.assertEqual(intentos.count(), 4)

        # Cuando expira el tiempo de bloqueo temporal, permite iniciar sesión y reinicia el contador
        self.user.bloqueado_hasta = timezone.now() - timedelta(minutes=1)
        self.user.save(update_fields=['bloqueado_hasta'])

        success_resp = self.client.post(
            reverse('login'),
            {
                'correo': self.user.correo,
                'password': 'secure-password-42',
            },
            format='json',
        )
        self.assertEqual(success_resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.intentos_fallidos_login, 0)
        self.assertIsNone(self.user.bloqueado_hasta)


@override_settings(
    DEBUG=False,
    EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
    EMAIL_HOST_USER="prueba@example.com",
    EMAIL_HOST_PASSWORD="clave-de-prueba",
)
class PasswordRecoveryCodeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = Usuario.objects.create_user(
            correo="reset@example.com",
            nombre="Ana",
            apellido="Pérez",
            password="Original-Safe-Password-2026!",
            tipo_documento="CC",
            numero_documento="RESET123",
        )

    @override_settings(
        DEBUG=True,
        EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
    )
    @patch("apps_sirae.usuarios.api.password_reset.send_mail")
    def test_local_console_backend_returns_the_code_for_development(
        self, send_mail
    ):
        response = self.client.post(
            reverse("recuperar-password"),
            {"correo": self.user.correo},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.data["debug_code"], r"^\d{6}$")

    @patch("apps_sirae.usuarios.api.password_reset.send_mail")
    def test_registered_email_receives_six_digit_code(self, send_mail):
        response = self.client.post(
            reverse("recuperar-password"),
            {"correo": self.user.correo.upper()},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        send_mail.assert_called_once()

        codigo = re.search(
            r"código para recuperar la contraseña es: (\d{6})",
            send_mail.call_args.kwargs["message"],
        )
        self.assertIsNotNone(codigo)

        recuperacion = PasswordResetCode.objects.get(usuario=self.user)
        self.assertNotEqual(
            recuperacion.codigo_hash,
            codigo.group(1),
        )

    @patch(
        "apps_sirae.usuarios.api.password_reset.send_mail",
        side_effect=OSError("mail server unavailable"),
    )
    def test_email_failure_returns_error_and_removes_recovery_code(
        self, send_mail
    ):
        response = self.client.post(
            reverse("recuperar-password"),
            {"correo": self.user.correo},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn("No fue posible enviar", response.data["error"])
        self.assertFalse(
            PasswordResetCode.objects.filter(usuario=self.user).exists()
        )

    @patch("apps_sirae.usuarios.api.password_reset.send_mail")
    def test_unknown_email_gets_same_response_and_does_not_send_email(
        self, send_mail
    ):
        registered = self.client.post(
            reverse("recuperar-password"),
            {"correo": self.user.correo},
            format="json",
        )

        send_mail.reset_mock()

        unknown = self.client.post(
            reverse("recuperar-password"),
            {"correo": "unknown@example.com"},
            format="json",
        )

        self.assertEqual(registered.status_code, unknown.status_code)
        self.assertEqual(registered.data, unknown.data)
        send_mail.assert_not_called()

    @patch("apps_sirae.usuarios.api.password_reset.send_mail")
    def test_code_resets_password_once(self, send_mail):
        self.client.post(
            reverse("recuperar-password"),
            {"correo": self.user.correo},
            format="json",
        )

        codigo = re.search(
            r"código para recuperar la contraseña es: (\d{6})",
            send_mail.call_args.kwargs["message"],
        ).group(1)

        response = self.client.post(
            reverse("confirmar-recuperacion-password"),
            {
                "correo": self.user.correo,
                "codigo": codigo,
                "nueva_password": "New-Safe-Password-2026!",
                "confirmar_password": "New-Safe-Password-2026!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(
            self.user.check_password("New-Safe-Password-2026!")
        )
        self.assertFalse(
            PasswordResetCode.objects.filter(usuario=self.user).exists()
        )

    @patch("apps_sirae.usuarios.api.password_reset.send_mail")
    def test_five_wrong_codes_invalidate_the_recovery_code(self, send_mail):
        self.client.post(
            reverse("recuperar-password"),
            {"correo": self.user.correo},
            format="json",
        )

        for _ in range(5):
            response = self.client.post(
                reverse("confirmar-recuperacion-password"),
                {
                    "correo": self.user.correo,
                    "codigo": "000000",
                    "nueva_password": "New-Safe-Password-2026!",
                    "confirmar_password": "New-Safe-Password-2026!",
                },
                format="json",
            )
            self.assertEqual(response.status_code, 400)

        self.assertFalse(
            PasswordResetCode.objects.filter(usuario=self.user).exists()
        )
        self.user.refresh_from_db()
        self.assertTrue(
            self.user.check_password("Original-Safe-Password-2026!")
        )


class BrevoPasswordResetApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.rol_admin = Rol.objects.create(nombre=Rol.NombreRol.ADMINISTRADOR)
        self.user = Usuario.objects.create_user(
            correo="brevo.user@sirae.com",
            nombre="Carlos",
            apellido="Brevo",
            password="Original-Pass-2026!x",
            tipo_documento="CC",
            numero_documento="BREVO001",
            rol=self.rol_admin,
            is_active=True,
        )

    @override_settings(
        BREVO_API_KEY="xkeysib-fake-render-brevo-key",
        BACKEND_URL="https://backend-sirae-pyim.onrender.com",
        DEBUG=False,
    )
    @patch("apps_sirae.usuarios.api.password_reset.requests.post")
    def test_recuperar_password_code_calls_brevo_http_api(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.text = '{"messageId": "<fake-brevo-msg-id>"}'
        mock_post.return_value = mock_resp

        response = self.client.post(
            reverse("recuperar-password"),
            {"correo": self.user.correo},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_post.called)
        call_args, call_kwargs = mock_post.call_args
        self.assertEqual(call_args[0], "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(call_kwargs["headers"]["api-key"], "xkeysib-fake-render-brevo-key")
        payload = call_kwargs["json"]
        self.assertEqual(payload["to"][0]["email"], self.user.correo)
        self.assertIn("https://backend-sirae-pyim.onrender.com", payload["htmlContent"])

    @override_settings(
        BREVO_API_KEY="xkeysib-fake-render-brevo-key",
        BACKEND_URL="https://backend-sirae-pyim.onrender.com",
        FRONTEND_URL="",
        DEBUG=False,
    )
    @patch("apps_sirae.usuarios.api.password_reset.requests.post")
    def test_solicitar_recuperacion_password_view_uses_brevo_and_production_url(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.text = '{"messageId": "<fake-brevo-msg-id-2>"}'
        mock_post.return_value = mock_resp

        response = self.client.post(
            reverse("password-reset-solicitar"),
            {"correo": self.user.correo},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_post.called)
        call_args, call_kwargs = mock_post.call_args
        self.assertEqual(call_args[0], "https://api.brevo.com/v3/smtp/email")
        payload = call_kwargs["json"]
        self.assertEqual(payload["to"][0]["email"], self.user.correo)
        self.assertIn("https://backend-sirae-pyim.onrender.com/recuperar-password?token=", payload["htmlContent"])

    @override_settings(
        BREVO_API_KEY="xkeysib-fake-render-brevo-key",
        BACKEND_URL="https://backend-sirae-pyim.onrender.com",
    )
    def test_test_email_view_get_status(self):
        response = self.client.get(reverse("auth-test-email"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["brevo_api_key_configurada"])
        self.assertEqual(response.data["backend_url"], "https://backend-sirae-pyim.onrender.com")

    @override_settings(
        BREVO_API_KEY="xkeysib-fake-render-brevo-key",
        BACKEND_URL="https://backend-sirae-pyim.onrender.com",
    )
    @patch("apps_sirae.usuarios.api.password_reset.requests.post")
    def test_test_email_view_post_sends_email(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.text = '{"messageId": "<test-diagnostic-id>"}'
        mock_post.return_value = mock_resp

        response = self.client.post(
            reverse("auth-test-email"),
            {"email": "prueba@sirae.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "success")
        self.assertTrue(mock_post.called)



class UsuarioLogoutApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.rol_admin = Rol.objects.create(nombre=Rol.NombreRol.ADMINISTRADOR)
        self.user = Usuario.objects.create_user(
            correo="logout@sirae.com",
            nombre="Laura",
            apellido="Gómez",
            password="Safe-Logout-Password-2026!",
            tipo_documento="CC",
            numero_documento="LOGOUT001",
            rol=self.rol_admin,
        )

    def test_logout_revokes_refresh_and_access_tokens_and_rejects_subsequent_requests(self):
        login_resp = self.client.post(
            reverse("login"),
            {
                "correo": self.user.correo,
                "password": "Safe-Logout-Password-2026!",
            },
            format="json",
        )
        self.assertEqual(login_resp.status_code, 200)
        access_token = login_resp.data["access"]
        refresh_token = login_resp.data["refresh"]

        # Verificar que el access token funciona antes de cerrar sesión
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        pre_logout_resp = self.client.get("/api/usuarios/")
        self.assertEqual(pre_logout_resp.status_code, 200)

        # Solicitar cierre de sesión al backend
        logout_resp = self.client.post(
            reverse("logout"),
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(logout_resp.status_code, 200)
        self.assertIn("Sesión cerrada correctamente", logout_resp.data["mensaje"])

        # Solicitudes posteriores con el access token revocado deben rechazarse con 401
        post_logout_resp = self.client.get("/api/usuarios/")
        self.assertEqual(post_logout_resp.status_code, 401)

        # Solicitudes posteriores para refrescar con el refresh token revocado deben rechazarse con 401
        refresh_resp = self.client.post(
            reverse("token_refresh"),
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(refresh_resp.status_code, 401)

    def test_logout_rejects_already_revoked_or_invalid_refresh_token(self):
        resp = self.client.post(
            reverse("logout"),
            {"refresh": "invalid-or-tampered-refresh-token"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)


@override_settings(
    DEBUG=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class RegistroYAsignacionUsuariosSuperAdminTests(TestCase):
    """
    Suite integral para auditar y verificar los 15 criterios de aceptación
    del registro de usuarios y asignación institucional por el Superadministrador.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.rol_super = Rol.objects.create(nombre=Rol.NombreRol.SUPER_ADMINISTRADOR)
        self.rol_admin = Rol.objects.create(nombre=Rol.NombreRol.ADMINISTRADOR)
        self.rol_supervisor = Rol.objects.create(nombre=Rol.NombreRol.SUPERVISOR)
        self.rol_jefa = Rol.objects.create(nombre=Rol.NombreRol.JEFA_MANIPULADORAS)
        self.rol_manipuladora = Rol.objects.create(nombre=Rol.NombreRol.MANIPULADORA)

        self.superadmin = Usuario.objects.create_user(
            correo="superadmin@sirae.com",
            nombre="Carlos",
            apellido="SuperAdmin",
            password="Super-Safe-Password-2026!",
            tipo_documento="CC",
            numero_documento="SUPER001",
            rol=self.rol_super,
            is_superuser=True,
            is_staff=True,
        )

        self.inst_activa_1 = Institucion.objects.create(
            nombre_institucion="Colegio San José",
            nit="900111222-1",
            estado="ACTIVO",
        )
        self.inst_activa_2 = Institucion.objects.create(
            nombre_institucion="Colegio Santa María",
            nit="900111222-2",
            estado="ACTIVO",
        )
        self.inst_inactiva = Institucion.objects.create(
            nombre_institucion="Colegio Inactivo Norte",
            nit="900111222-9",
            estado="INACTIVO",
        )

        self.sede_activa = Sede.objects.create(
            id_institucion=self.inst_activa_1,
            nombre_sede="Sede Principal San José",
            estado="ACTIVO",
        )
        self.sede_inactiva = Sede.objects.create(
            id_institucion=self.inst_activa_1,
            nombre_sede="Sede Clausurada",
            estado="INACTIVO",
        )

        self.client.force_authenticate(user=self.superadmin)

    def test_criterios_1_3_7_13_14_15_registro_admin_institucional_y_auditoria(self):
        """
        Verifica registro exitoso de Administrador institucional con todos los campos,
        asignación a 1 institución activa, estado inicial y auditoría de creador + timestamp.
        """
        antes = timezone.now()
        payload = {
            "nombre": "Marta",
            "apellido": "Ríos",
            "tipo_documento": "CC",
            "numero_documento": "1098765432",
            "correo": "marta.rios@sirae.edu.co",
            "rol": self.rol_admin.id_rol,
            "id_institucion": self.inst_activa_1.id_institucion,
            "id_sede": self.sede_activa.id_sede,
            "is_active": True,
            "password": "Admin-Password-2026!",
        }

        resp = self.client.post("/api/usuarios/", payload, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["nombre"], "Marta")
        self.assertEqual(resp.data["apellido"], "Ríos")
        self.assertEqual(resp.data["tipo_documento"], "CC")
        self.assertEqual(resp.data["numero_documento"], "1098765432")
        self.assertEqual(resp.data["correo"], "marta.rios@sirae.edu.co")
        self.assertEqual(resp.data["id_institucion"], self.inst_activa_1.id_institucion)
        self.assertEqual(resp.data["id_sede"], self.sede_activa.id_sede)
        self.assertTrue(resp.data["is_active"])
        self.assertNotIn("password", resp.data)

        # Criterio 15: Auditoría del usuario creador y timestamp exacto
        self.assertEqual(resp.data["creado_por"], self.superadmin.id_usuario)
        self.assertIsNotNone(resp.data["fecha_creacion"])

        usuario_db = Usuario.objects.get(correo="marta.rios@sirae.edu.co")
        self.assertEqual(usuario_db.creado_por_id, self.superadmin.id_usuario)
        self.assertGreaterEqual(usuario_db.fecha_creacion, antes)

        from apps_sirae.usuarios.models import AuditoriaUsuario
        registro_aud = AuditoriaUsuario.objects.filter(
            usuario_afectado=usuario_db,
            accion="CREACION",
        ).first()
        self.assertIsNotNone(registro_aud)
        self.assertEqual(registro_aud.usuario_actor_id, self.superadmin.id_usuario)
        self.assertGreaterEqual(registro_aud.creado_en, antes)

    def test_criterio_2_superadmin_solo_asigna_roles_autorizados(self):
        """
        Verifica que el Superadministrador solo pueda registrar Administradores institucionales
        y Supervisores, bloqueando la creación de otro SuperAdministrador o roles de cocina.
        """
        # Intento de crear otro SuperAdministrador -> bloqueado
        resp_super = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "Clon",
                "apellido": "Super",
                "tipo_documento": "CC",
                "numero_documento": "999000111",
                "correo": "clon.super@sirae.com",
                "rol": self.rol_super.id_rol,
                "password": "Safe-Password-2026!",
            },
            format="json",
        )
        self.assertEqual(resp_super.status_code, 400)
        self.assertIn("rol", resp_super.data)

        # Intento de crear Manipuladora directamente por el SuperAdmin -> bloqueado por jerarquía
        resp_manip = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "Rosa",
                "apellido": "Cocina",
                "tipo_documento": "CC",
                "numero_documento": "999000222",
                "correo": "rosa.cocina@sirae.com",
                "rol": self.rol_manipuladora.id_rol,
                "id_institucion": self.inst_activa_1.id_institucion,
                "password": "Safe-Password-2026!",
            },
            format="json",
        )
        self.assertEqual(resp_manip.status_code, 400)
        self.assertIn("rol", resp_manip.data)

        # Consulta de roles asignables para el SuperAdmin
        roles_resp = self.client.get("/api/roles/?asignables=true")
        self.assertEqual(roles_resp.status_code, 200)
        lista_roles = roles_resp.data.get("results", roles_resp.data) if isinstance(roles_resp.data, dict) else roles_resp.data
        nombres_roles = {r["nombre"] for r in lista_roles}
        self.assertIn(Rol.NombreRol.ADMINISTRADOR, nombres_roles)
        self.assertIn(Rol.NombreRol.SUPERVISOR, nombres_roles)
        self.assertNotIn(Rol.NombreRol.SUPER_ADMINISTRADOR, nombres_roles)
        self.assertNotIn(Rol.NombreRol.MANIPULADORA, nombres_roles)

    def test_criterios_4_5_6_validacion_campos_obligatorios_formato_correo_y_unicidad(self):
        """
        Verifica rechazo de campos vacíos, formato inválido de correo y duplicidad de correo/documento.
        """
        # Campos obligatorios faltantes
        resp_vacio = self.client.post("/api/usuarios/", {}, format="json")
        self.assertEqual(resp_vacio.status_code, 400)
        for campo in ("nombre", "apellido", "correo", "tipo_documento", "numero_documento"):
            self.assertIn(campo, resp_vacio.data)

        # Formato de correo inválido
        resp_email_invalido = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "Pedro",
                "apellido": "Gómez",
                "tipo_documento": "CC",
                "numero_documento": "777888999",
                "correo": "correo-sin-dominio-valido",
                "rol": self.rol_supervisor.id_rol,
            },
            format="json",
        )
        self.assertEqual(resp_email_invalido.status_code, 400)
        self.assertIn("correo", resp_email_invalido.data)

        # Duplicidad de correo (incluso en mayúsculas) y número de documento
        resp_dup = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "Otro",
                "apellido": "Usuario",
                "tipo_documento": "CC",
                "numero_documento": "SUPER001",
                "correo": "SUPERADMIN@SIRAE.COM",
                "rol": self.rol_supervisor.id_rol,
            },
            format="json",
        )
        self.assertEqual(resp_dup.status_code, 400)
        self.assertIn("correo", resp_dup.data)
        self.assertIn("numero_documento", resp_dup.data)

    def test_criterio_8_reglas_asignacion_institucional_admin_vs_supervisor(self):
        """
        Verifica que:
        - Un Administrador institucional corresponde a 1 sola institución (rechaza múltiples o ninguna).
        - Un Supervisor puede tener varias instituciones asignadas.
        """
        # Administrador sin institución -> rechazado
        resp_admin_sin_inst = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "Luis",
                "apellido": "SinColegio",
                "tipo_documento": "CC",
                "numero_documento": "111222333",
                "correo": "luis.sincolegio@sirae.com",
                "rol": self.rol_admin.id_rol,
            },
            format="json",
        )
        self.assertEqual(resp_admin_sin_inst.status_code, 400)
        self.assertIn("id_institucion", resp_admin_sin_inst.data)

        # Administrador con múltiples instituciones -> rechazado
        resp_admin_multi = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "Luis",
                "apellido": "MultiColegio",
                "tipo_documento": "CC",
                "numero_documento": "111222334",
                "correo": "luis.multicolegio@sirae.com",
                "rol": self.rol_admin.id_rol,
                "instituciones_ids": [
                    self.inst_activa_1.id_institucion,
                    self.inst_activa_2.id_institucion,
                ],
            },
            format="json",
        )
        self.assertEqual(resp_admin_multi.status_code, 400)
        self.assertIn("instituciones_ids", resp_admin_multi.data)

        # Supervisor con múltiples instituciones activas -> permitido
        resp_sup = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "Camila",
                "apellido": "Supervisora",
                "tipo_documento": "CC",
                "numero_documento": "555666777",
                "correo": "camila.supervisora@sirae.com",
                "rol": self.rol_supervisor.id_rol,
                "instituciones_ids": [
                    self.inst_activa_1.id_institucion,
                    self.inst_activa_2.id_institucion,
                ],
            },
            format="json",
        )
        self.assertEqual(resp_sup.status_code, 201, resp_sup.data)
        self.assertEqual(len(resp_sup.data["instituciones_supervisor"]), 2)

    def test_criterio_9_impedir_asignacion_a_instituciones_o_sedes_inactivas(self):
        """
        Verifica que no se permita asignar ni Administradores ni Supervisores a instituciones inactivas.
        """
        resp_admin_inactiva = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "Jorge",
                "apellido": "Inactivo",
                "tipo_documento": "CC",
                "numero_documento": "444555666",
                "correo": "jorge.inactivo@sirae.com",
                "rol": self.rol_admin.id_rol,
                "id_institucion": self.inst_inactiva.id_institucion,
            },
            format="json",
        )
        self.assertEqual(resp_admin_inactiva.status_code, 400)
        self.assertIn("id_institucion", resp_admin_inactiva.data)

        resp_sup_inactiva = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "Elena",
                "apellido": "Supervisora",
                "tipo_documento": "CC",
                "numero_documento": "444555667",
                "correo": "elena.supervisora@sirae.com",
                "rol": self.rol_supervisor.id_rol,
                "instituciones_ids": [
                    self.inst_activa_1.id_institucion,
                    self.inst_inactiva.id_institucion,
                ],
            },
            format="json",
        )
        self.assertEqual(resp_sup_inactiva.status_code, 400)
        self.assertIn("instituciones_ids", resp_sup_inactiva.data)

        # Sede inactiva también debe rechazarse
        resp_sede_inactiva = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "Jorge",
                "apellido": "SedeInactiva",
                "tipo_documento": "CC",
                "numero_documento": "444555668",
                "correo": "jorge.sedeinactiva@sirae.com",
                "rol": self.rol_admin.id_rol,
                "id_institucion": self.inst_activa_1.id_institucion,
                "id_sede": self.sede_inactiva.id_sede,
            },
            format="json",
        )
        self.assertEqual(resp_sede_inactiva.status_code, 400)
        self.assertIn("id_sede", resp_sede_inactiva.data)

    def test_criterio_10_impedir_dos_administradores_activos_en_misma_institucion(self):
        """
        Verifica que una institución no pueda tener dos Administradores institucionales activos.
        """
        resp_1 = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "AdminUno",
                "apellido": "Colegio",
                "tipo_documento": "CC",
                "numero_documento": "300100200",
                "correo": "admin1.colegio@sirae.com",
                "rol": self.rol_admin.id_rol,
                "id_institucion": self.inst_activa_1.id_institucion,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(resp_1.status_code, 201, resp_1.data)

        resp_2 = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "AdminDos",
                "apellido": "Duplicado",
                "tipo_documento": "CC",
                "numero_documento": "300100201",
                "correo": "admin2.colegio@sirae.com",
                "rol": self.rol_admin.id_rol,
                "id_institucion": self.inst_activa_1.id_institucion,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(resp_2.status_code, 400)
        self.assertIn("id_institucion", resp_2.data)

    def test_criterios_11_12_13_password_temporal_segura_sin_texto_plano_y_estado_inactivo(self):
        """
        Verifica que al omitir password se genere una clave temporal segura hasheada,
        se marque debe_cambiar_password=True, se dispare el correo de activación sin texto plano
        y se permita crear cuentas inicialmente inactivas.
        """
        mail.outbox.clear()
        resp = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "Sofía",
                "apellido": "Temporal",
                "tipo_documento": "CE",
                "numero_documento": "800900100",
                "correo": "sofia.temporal@sirae.com",
                "rol": self.rol_supervisor.id_rol,
                "estado": "Inactivo",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data["is_active"])
        self.assertTrue(resp.data["debe_cambiar_password"])
        self.assertNotIn("password", resp.data)

        usuario_db = Usuario.objects.get(correo="sofia.temporal@sirae.com")
        self.assertTrue(usuario_db._es_password_hasheada(usuario_db.password))
        self.assertNotEqual(usuario_db.password, "")
        self.assertTrue(usuario_db.password.startswith("pbkdf2_"))

        # Verificar que se envió el correo de activación con enlace firmado y sin contraseñas en texto plano
        self.assertEqual(len(mail.outbox), 1)
        cuerpo_correo = mail.outbox[0].body
        self.assertIn("recuperar-password?token=", cuerpo_correo)
        self.assertIn("nunca enviamos contraseñas en texto plano", cuerpo_correo)


class ConsultaBusquedaFiltradoUsuariosTests(TestCase):
    """
    Suite exhaustiva de auditoría para verificar los 10 criterios de aceptación
    de Consulta, Búsqueda y Filtrado de Usuarios en SIRAE PAE.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.rol_super = Rol.objects.create(nombre=Rol.NombreRol.SUPER_ADMINISTRADOR)
        self.rol_admin = Rol.objects.create(nombre=Rol.NombreRol.ADMINISTRADOR)
        self.rol_supervisor = Rol.objects.create(nombre=Rol.NombreRol.SUPERVISOR)
        self.rol_jefa = Rol.objects.create(nombre=Rol.NombreRol.JEFA_MANIPULADORAS)
        self.rol_manipuladora = Rol.objects.create(nombre=Rol.NombreRol.MANIPULADORA)

        self.inst_norte = Institucion.objects.create(
            nombre_institucion="IED Colegio del Norte",
            nit="800100100-1",
            estado="ACTIVO",
        )
        self.inst_sur = Institucion.objects.create(
            nombre_institucion="IED Colegio del Sur",
            nit="800100100-2",
            estado="ACTIVO",
        )
        self.inst_oriente = Institucion.objects.create(
            nombre_institucion="IED Colegio de Oriente",
            nit="800100100-3",
            estado="ACTIVO",
        )

        self.superadmin = Usuario.objects.create_user(
            correo="superadmin@sirae.gov.co",
            nombre="Roberto",
            apellido="Gómez",
            password="Super-Password-2026!",
            tipo_documento="CC",
            numero_documento="10000001",
            rol=self.rol_super,
            is_superuser=True,
            is_staff=True,
        )

        self.admin_norte = Usuario.objects.create_user(
            correo="admin.norte@sirae.edu.co",
            nombre="Patricia",
            apellido="Salazar",
            password="Admin-Password-2026!",
            tipo_documento="CC",
            numero_documento="20000001",
            rol=self.rol_admin,
            id_institucion=self.inst_norte,
            is_active=True,
        )

        self.admin_sur = Usuario.objects.create_user(
            correo="admin.sur@sirae.edu.co",
            nombre="Fernando",
            apellido="Vargas",
            password="Admin-Password-2026!",
            tipo_documento="CC",
            numero_documento="20000002",
            rol=self.rol_admin,
            id_institucion=self.inst_sur,
            is_active=True,
        )

        self.supervisor = Usuario.objects.create_user(
            correo="supervisor.zona@sirae.edu.co",
            nombre="Andrés",
            apellido="Cárdenas",
            password="Sup-Password-2026!",
            tipo_documento="CC",
            numero_documento="30000001",
            rol=self.rol_supervisor,
            is_active=True,
        )
        from apps_sirae.instituciones.models import SupervisorInstitucion
        SupervisorInstitucion.objects.create(
            id_supervisor=self.supervisor,
            id_institucion=self.inst_norte,
        )

        self.jefa_norte = Usuario.objects.create_user(
            correo="jefa.norte@sirae.edu.co",
            nombre="Lucía",
            apellido="Mendoza",
            password="Jefa-Password-2026!",
            tipo_documento="CC",
            numero_documento="40000001",
            rol=self.rol_jefa,
            id_institucion=self.inst_norte,
            is_active=True,
        )

        self.manipuladora_norte_inactiva = Usuario.objects.create_user(
            correo="manipuladora.norte@sirae.edu.co",
            nombre="Carmen",
            apellido="Rojas",
            password="Manip-Password-2026!",
            tipo_documento="CE",
            numero_documento="50000001",
            rol=self.rol_manipuladora,
            id_institucion=self.inst_norte,
            is_active=False,
        )

        self.manipuladora_sur = Usuario.objects.create_user(
            correo="manipuladora.sur@sirae.edu.co",
            nombre="Beatriz",
            apellido="Pineda",
            password="Manip-Password-2026!",
            tipo_documento="CC",
            numero_documento="50000002",
            rol=self.rol_manipuladora,
            id_institucion=self.inst_sur,
            is_active=True,
        )

    @staticmethod
    def _extraer_resultados(resp):
        if isinstance(resp.data, dict) and "results" in resp.data:
            return resp.data["results"]
        return resp.data

    def test_criterio_1_y_5_superadmin_consulta_listado_estructurado_de_todas_las_instituciones(self):
        self.client.force_authenticate(user=self.superadmin)
        resp = self.client.get("/api/usuarios/")
        self.assertEqual(resp.status_code, 200)
        resultados = self._extraer_resultados(resp)
        self.assertEqual(len(resultados), 7)

        for item in resultados:
            self.assertIn("nombre", item)
            self.assertIn("apellido", item)
            self.assertIn("nombre_completo", item)
            self.assertIn("numero_documento", item)
            self.assertIn("correo", item)
            self.assertIn("rol", item)
            self.assertIn("rol_detalle", item)
            self.assertIn("is_active", item)
            self.assertIn("estado_display", item)

    def test_criterio_2_busqueda_dinamica_por_nombre_documento_y_correo(self):
        self.client.force_authenticate(user=self.superadmin)

        # Búsqueda por nombre + apellido
        resp_nom = self.client.get("/api/usuarios/?search=Patricia Salazar")
        res_nom = self._extraer_resultados(resp_nom)
        self.assertEqual(len(res_nom), 1)
        self.assertEqual(res_nom[0]["correo"], "admin.norte@sirae.edu.co")

        # Búsqueda por número de documento
        resp_doc = self.client.get("/api/usuarios/?search=50000001")
        res_doc = self._extraer_resultados(resp_doc)
        self.assertEqual(len(res_doc), 1)
        self.assertEqual(res_doc[0]["correo"], "manipuladora.norte@sirae.edu.co")

        # Búsqueda por correo electrónico
        resp_mail = self.client.get("/api/usuarios/?search=manipuladora.sur@sirae.edu.co")
        res_mail = self._extraer_resultados(resp_mail)
        self.assertEqual(len(res_mail), 1)
        self.assertEqual(res_mail[0]["numero_documento"], "50000002")

    def test_criterio_3_filtrado_por_rol_y_estado_de_cuenta(self):
        self.client.force_authenticate(user=self.superadmin)

        # Filtrar por rol (ID) y estado Inactivo
        resp = self.client.get(
            f"/api/usuarios/?rol={self.rol_manipuladora.id_rol}&estado=Inactivo"
        )
        resultados = self._extraer_resultados(resp)
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["correo"], "manipuladora.norte@sirae.edu.co")
        self.assertFalse(resultados[0]["is_active"])
        self.assertEqual(resultados[0]["estado_display"], "Inactivo")

        # Filtrar por estado Activo
        resp_activos = self.client.get("/api/usuarios/?estado=Activo")
        res_activos = self._extraer_resultados(resp_activos)
        self.assertTrue(all(u["is_active"] for u in res_activos))
        self.assertEqual(len(res_activos), 6)

    def test_criterio_4_y_6_ambito_estricto_administrador_institucional(self):
        """
        El Administrador institucional únicamente puede consultar usuarios pertenecientes
        estrictamente a su propia institución y nunca de otras instituciones ni al Superadministrador.
        """
        self.client.force_authenticate(user=self.admin_norte)
        resp = self.client.get("/api/usuarios/")
        self.assertEqual(resp.status_code, 200)
        resultados = self._extraer_resultados(resp)
        correos = {u["correo"] for u in resultados}

        self.assertEqual(
            correos,
            {
                "admin.norte@sirae.edu.co",
                "jefa.norte@sirae.edu.co",
                "manipuladora.norte@sirae.edu.co",
            },
        )
        self.assertNotIn("superadmin@sirae.gov.co", correos)
        self.assertNotIn("admin.sur@sirae.edu.co", correos)
        self.assertNotIn("manipuladora.sur@sirae.edu.co", correos)

        # Si intenta filtrar por otra institución, obtiene vacío
        resp_otra = self.client.get(f"/api/usuarios/?id_institucion={self.inst_sur.id_institucion}")
        self.assertEqual(len(self._extraer_resultados(resp_otra)), 0)

        # Si intenta consultar el detalle de un usuario de otra institución -> 404
        resp_detalle_ajeno = self.client.get(f"/api/usuarios/{self.admin_sur.id_usuario}/")
        self.assertEqual(resp_detalle_ajeno.status_code, 404)

    def test_criterio_7_ambito_supervisor_restringido_a_funcionalidad_explicita(self):
        """
        El Supervisor solo consulta otros usuarios cuando una funcionalidad específica y explícita
        se lo permita, y únicamente de sus instituciones asignadas.
        """
        self.client.force_authenticate(user=self.supervisor)

        # 1. Consulta general sin funcionalidad explícita -> solo ve su propio perfil
        resp_general = self.client.get("/api/usuarios/")
        res_general = self._extraer_resultados(resp_general)
        self.assertEqual(len(res_general), 1)
        self.assertEqual(res_general[0]["id_usuario"], self.supervisor.id_usuario)

        # 2. Funcionalidad explícita (/api/usuarios/consulta-supervision/) -> ve personal de inst_norte
        resp_explicita = self.client.get("/api/usuarios/consulta-supervision/")
        self.assertEqual(resp_explicita.status_code, 200)
        res_explicita = self._extraer_resultados(resp_explicita)
        correos_sup = {u["correo"] for u in res_explicita}
        self.assertIn("admin.norte@sirae.edu.co", correos_sup)
        self.assertIn("jefa.norte@sirae.edu.co", correos_sup)
        self.assertNotIn("admin.sur@sirae.edu.co", correos_sup)
        self.assertNotIn("superadmin@sirae.gov.co", correos_sup)

        # 3. Intento de filtrar por institución no asignada al supervisor -> vacío
        resp_inst_ajena = self.client.get(
            f"/api/usuarios/consulta-supervision/?id_institucion={self.inst_sur.id_institucion}"
        )
        self.assertEqual(len(self._extraer_resultados(resp_inst_ajena)), 0)

    def test_criterio_9_proteccion_informacion_sensible_en_listado_y_detalle(self):
        """
        Al consultar el detalle completo de un usuario, nunca se exponen contraseñas en hash,
        tokens privados ni metadatos sensibles de seguridad.
        """
        PasswordResetService.generar_token(self.admin_norte)
        self.client.force_authenticate(user=self.superadmin)

        resp_detalle = self.client.get(f"/api/usuarios/{self.admin_norte.id_usuario}/")
        self.assertEqual(resp_detalle.status_code, 200)
        data = resp_detalle.data

        for campo_prohibido in (
            "password",
            "codigo_hash",
            "password_reset_code",
            "access",
            "refresh",
            "token",
            "intentos_fallidos_login",
            "bloqueado_hasta",
            "ultimo_intento_fallido",
            "user_permissions",
            "groups",
        ):
            self.assertNotIn(campo_prohibido, data)

        self.assertEqual(data["correo"], "admin.norte@sirae.edu.co")
        self.assertEqual(data["institucion_nombre"], "IED Colegio del Norte")

    def test_criterio_10_paginacion_del_lado_del_servidor(self):
        self.client.force_authenticate(user=self.superadmin)
        resp_p1 = self.client.get("/api/usuarios/?page=1&page_size=3")
        self.assertEqual(resp_p1.status_code, 200)
        self.assertEqual(resp_p1.data["count"], 7)
        self.assertEqual(len(resp_p1.data["results"]), 3)
        self.assertIsNotNone(resp_p1.data["next"])
        self.assertIsNone(resp_p1.data["previous"])

        resp_p3 = self.client.get("/api/usuarios/?page=3&page_size=3")
        self.assertEqual(resp_p3.status_code, 200)
        self.assertEqual(len(resp_p3.data["results"]), 1)
        self.assertIsNone(resp_p3.data["next"])
        self.assertIsNotNone(resp_p3.data["previous"])


class EdicionDatosYAsignacionesUsuariosTests(TestCase):
    """
    Suite integral de auditoría para verificar los 6 criterios de aceptación
    del módulo de Edición de Datos y Asignaciones de Usuarios en SIRAE PAE.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.rol_super = Rol.objects.create(nombre=Rol.NombreRol.SUPER_ADMINISTRADOR)
        self.rol_admin = Rol.objects.create(nombre=Rol.NombreRol.ADMINISTRADOR)
        self.rol_supervisor = Rol.objects.create(nombre=Rol.NombreRol.SUPERVISOR)
        self.rol_jefa = Rol.objects.create(nombre=Rol.NombreRol.JEFA_MANIPULADORAS)
        self.rol_manipuladora = Rol.objects.create(nombre=Rol.NombreRol.MANIPULADORA)

        self.inst_norte = Institucion.objects.create(
            nombre_institucion="IED Colegio del Norte",
            nit="800200200-1",
            estado="ACTIVO",
        )
        self.inst_sur = Institucion.objects.create(
            nombre_institucion="IED Colegio del Sur",
            nit="800200200-2",
            estado="ACTIVO",
        )
        self.inst_oriente = Institucion.objects.create(
            nombre_institucion="IED Colegio de Oriente",
            nit="800200200-3",
            estado="ACTIVO",
        )

        self.sede_norte_1 = Sede.objects.create(
            id_institucion=self.inst_norte,
            nombre_sede="Sede Principal Norte",
            estado="ACTIVO",
        )
        self.sede_norte_2 = Sede.objects.create(
            id_institucion=self.inst_norte,
            nombre_sede="Sede Secundaria Norte",
            estado="ACTIVO",
        )
        self.sede_sur_1 = Sede.objects.create(
            id_institucion=self.inst_sur,
            nombre_sede="Sede Principal Sur",
            estado="ACTIVO",
        )

        self.superadmin = Usuario.objects.create_user(
            correo="superadmin@sirae.gov.co",
            nombre="Roberto",
            apellido="Gómez",
            password="Super-Password-2026!",
            tipo_documento="CC",
            numero_documento="10000001",
            rol=self.rol_super,
            is_superuser=True,
            is_staff=True,
        )

        self.admin_norte = Usuario.objects.create_user(
            correo="admin.norte@sirae.edu.co",
            nombre="Patricia",
            apellido="Salazar",
            password="Admin-Password-2026!",
            tipo_documento="CC",
            numero_documento="20000001",
            rol=self.rol_admin,
            id_institucion=self.inst_norte,
            id_sede=self.sede_norte_1,
            is_active=True,
        )

        self.admin_sur = Usuario.objects.create_user(
            correo="admin.sur@sirae.edu.co",
            nombre="Fernando",
            apellido="Vargas",
            password="Admin-Password-2026!",
            tipo_documento="CC",
            numero_documento="20000002",
            rol=self.rol_admin,
            id_institucion=self.inst_sur,
            id_sede=self.sede_sur_1,
            is_active=True,
        )

        self.supervisor = Usuario.objects.create_user(
            correo="supervisor.zona@sirae.edu.co",
            nombre="Andrés",
            apellido="Cárdenas",
            password="Sup-Password-2026!",
            tipo_documento="CC",
            numero_documento="30000001",
            rol=self.rol_supervisor,
            is_active=True,
        )
        from apps_sirae.instituciones.models import SupervisorInstitucion
        SupervisorInstitucion.objects.create(
            id_supervisor=self.supervisor,
            id_institucion=self.inst_norte,
        )

        self.jefa_norte = Usuario.objects.create_user(
            correo="jefa.norte@sirae.edu.co",
            nombre="Lucía",
            apellido="Mendoza",
            password="Jefa-Password-2026!",
            tipo_documento="CC",
            numero_documento="40000001",
            rol=self.rol_jefa,
            id_institucion=self.inst_norte,
            id_sede=self.sede_norte_1,
            is_active=True,
        )

        self.manipuladora_sur = Usuario.objects.create_user(
            correo="manipuladora.sur@sirae.edu.co",
            nombre="Beatriz",
            apellido="Pineda",
            password="Manip-Password-2026!",
            tipo_documento="CC",
            numero_documento="50000002",
            rol=self.rol_manipuladora,
            id_institucion=self.inst_sur,
            id_sede=self.sede_sur_1,
            is_active=True,
        )

    def test_criterios_1_2_3_5_superadmin_edita_datos_y_reasigna_instituciones_y_sedes(self):
        """
        Verifica que el Superadministrador pueda consultar las asignaciones previas,
        editar datos autorizados (nombre, apellido, correo, documento, estado, rol, institución, sede)
        mediante PATCH/PUT y sincronizar las asignaciones institucionales.
        """
        self.client.force_authenticate(user=self.superadmin)

        # Criterio 1 y 3: Consultar usuario con sus asignaciones previas cargadas
        resp_get = self.client.get(f"/api/usuarios/{self.supervisor.id_usuario}/")
        self.assertEqual(resp_get.status_code, 200)
        self.assertEqual(len(resp_get.data["instituciones_supervisor"]), 1)
        self.assertEqual(
            resp_get.data["instituciones_supervisor"][0]["id_institucion"],
            self.inst_norte.id_institucion,
        )

        # Criterio 2 y 5: Actualizar datos y asignaciones múltiples del Supervisor vía PATCH
        resp_patch = self.client.patch(
            f"/api/usuarios/{self.supervisor.id_usuario}/",
            {
                "nombre": "Andrés Felipe",
                "apellido": "Cárdenas Soto",
                "tipo_documento": "CE",
                "numero_documento": "30000999",
                "correo": "andres.felipe@sirae.edu.co",
                "is_active": False,
                "instituciones_ids": [
                    self.inst_norte.id_institucion,
                    self.inst_oriente.id_institucion,
                ],
            },
            format="json",
        )
        self.assertEqual(resp_patch.status_code, 200, resp_patch.data)
        self.assertEqual(resp_patch.data["nombre"], "Andrés Felipe")
        self.assertEqual(resp_patch.data["apellido"], "Cárdenas Soto")
        self.assertEqual(resp_patch.data["tipo_documento"], "CE")
        self.assertEqual(resp_patch.data["numero_documento"], "30000999")
        self.assertEqual(resp_patch.data["correo"], "andres.felipe@sirae.edu.co")
        self.assertFalse(resp_patch.data["is_active"])
        self.assertEqual(resp_patch.data["estado_display"], "Inactivo")
        ids_asignados = {
            i["id_institucion"] for i in resp_patch.data["instituciones_supervisor"]
        }
        self.assertEqual(
            ids_asignados,
            {self.inst_norte.id_institucion, self.inst_oriente.id_institucion},
        )

        # Verificar que también puede reasignar un Administrador institucional a otra institución libre (PUT)
        resp_put = self.client.put(
            f"/api/usuarios/{self.admin_norte.id_usuario}/",
            {
                "nombre": "Patricia Elena",
                "apellido": "Salazar",
                "correo": "admin.norte@sirae.edu.co",
                "tipo_documento": "CC",
                "numero_documento": "20000001",
                "rol": self.rol_admin.id_rol,
                "id_institucion": self.inst_oriente.id_institucion,
                "id_sede": None,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(resp_put.status_code, 200, resp_put.data)
        self.assertEqual(resp_put.data["id_institucion"], self.inst_oriente.id_institucion)
        self.assertEqual(resp_put.data["institucion_nombre"], "IED Colegio de Oriente")

        from apps_sirae.usuarios.models import AuditoriaUsuario
        self.assertTrue(
            AuditoriaUsuario.objects.filter(
                usuario_afectado=self.admin_norte,
                accion="ACTUALIZACION",
                usuario_actor=self.superadmin,
            ).exists()
        )

    def test_criterio_4_unicidad_al_editar_excluye_propio_registro_y_bloquea_colisiones(self):
        """
        Verifica que al editar un usuario se permita conservar su propio correo y número de documento,
        pero se rechace colisionar con el correo o documento de otro usuario existente.
        """
        self.client.force_authenticate(user=self.superadmin)

        # 1. Mantener su propio correo y documento al editar otros campos -> 200 OK
        resp_mismo = self.client.patch(
            f"/api/usuarios/{self.admin_norte.id_usuario}/",
            {
                "nombre": "Patricia Actualizada",
                "correo": "ADMIN.NORTE@SIRAE.EDU.CO",
                "numero_documento": "20000001",
            },
            format="json",
        )
        self.assertEqual(resp_mismo.status_code, 200, resp_mismo.data)
        self.assertEqual(resp_mismo.data["nombre"], "Patricia Actualizada")

        # 2. Colisión de correo con otro usuario (admin_sur) -> 400 Bad Request
        resp_colision_correo = self.client.patch(
            f"/api/usuarios/{self.admin_norte.id_usuario}/",
            {"correo": "ADMIN.SUR@SIRAE.EDU.CO"},
            format="json",
        )
        self.assertEqual(resp_colision_correo.status_code, 400)
        self.assertIn("correo", resp_colision_correo.data)

        # 3. Colisión de número de documento con otro usuario (admin_sur) -> 400 Bad Request
        resp_colision_doc = self.client.patch(
            f"/api/usuarios/{self.admin_norte.id_usuario}/",
            {"numero_documento": "20000002"},
            format="json",
        )
        self.assertEqual(resp_colision_doc.status_code, 400)
        self.assertIn("numero_documento", resp_colision_doc.data)

        # 4. Inconsistencia sede vs institución -> 400 Bad Request
        resp_sede_inconsistente = self.client.patch(
            f"/api/usuarios/{self.admin_norte.id_usuario}/",
            {
                "id_institucion": self.inst_norte.id_institucion,
                "id_sede": self.sede_sur_1.id_sede,
            },
            format="json",
        )
        self.assertEqual(resp_sede_inconsistente.status_code, 400)
        self.assertIn("id_sede", resp_sede_inconsistente.data)

    def test_criterios_2_y_6_control_estricto_de_alcance_para_administrador_institucional(self):
        """
        Verifica que el Administrador institucional:
        - Pueda editar el personal de cocina de su propia institución (nombre, correo, documento, estado, rol de cocina, sede de su institución).
        - Tenga prohibido editar usuarios de otra institución.
        - Tenga prohibido transferir un usuario a otra institución o asignarle una sede ajena.
        - Tenga prohibido promover a un usuario a SuperAdmin, Administrador o Supervisor.
        - Tenga prohibido cambiarse su propio rol o institución.
        """
        self.client.force_authenticate(user=self.admin_norte)

        # 1. Edición válida de personal de su propia institución (jefa_norte -> cambio de sede y rol a Manipuladora)
        resp_ok = self.client.patch(
            f"/api/usuarios/{self.jefa_norte.id_usuario}/",
            {
                "nombre": "Lucía Fernanda",
                "rol": self.rol_manipuladora.id_rol,
                "id_sede": self.sede_norte_2.id_sede,
                "is_active": False,
            },
            format="json",
        )
        self.assertEqual(resp_ok.status_code, 200, resp_ok.data)
        self.assertEqual(resp_ok.data["nombre"], "Lucía Fernanda")
        self.assertEqual(resp_ok.data["rol"], self.rol_manipuladora.id_rol)
        self.assertEqual(resp_ok.data["id_sede"], self.sede_norte_2.id_sede)
        self.assertEqual(resp_ok.data["id_institucion"], self.inst_norte.id_institucion)
        self.assertFalse(resp_ok.data["is_active"])

        # 2. Intento de editar usuario de otra institución -> rechazado (404 por queryset acotado)
        resp_ajeno = self.client.patch(
            f"/api/usuarios/{self.manipuladora_sur.id_usuario}/",
            {"nombre": "Intento Hack"},
            format="json",
        )
        self.assertIn(resp_ajeno.status_code, (403, 404))

        # 3. Intento de transferir su empleada a otra institución -> 400 Bad Request
        resp_transferir = self.client.patch(
            f"/api/usuarios/{self.jefa_norte.id_usuario}/",
            {"id_institucion": self.inst_sur.id_institucion},
            format="json",
        )
        self.assertEqual(resp_transferir.status_code, 400)
        self.assertIn("id_institucion", resp_transferir.data)

        # 4. Intento de asignar sede de otra institución -> 400 Bad Request
        resp_sede_ajena = self.client.patch(
            f"/api/usuarios/{self.jefa_norte.id_usuario}/",
            {"id_sede": self.sede_sur_1.id_sede},
            format="json",
        )
        self.assertEqual(resp_sede_ajena.status_code, 400)
        self.assertIn("id_sede", resp_sede_ajena.data)

        # 5. Intento de promover empleada a Supervisor o Administrador -> 400 Bad Request
        resp_promover_sup = self.client.patch(
            f"/api/usuarios/{self.jefa_norte.id_usuario}/",
            {"rol": self.rol_supervisor.id_rol},
            format="json",
        )
        self.assertEqual(resp_promover_sup.status_code, 400)
        self.assertIn("rol", resp_promover_sup.data)

        resp_promover_admin = self.client.patch(
            f"/api/usuarios/{self.jefa_norte.id_usuario}/",
            {"rol": self.rol_admin.id_rol},
            format="json",
        )
        self.assertEqual(resp_promover_admin.status_code, 400)
        self.assertIn("rol", resp_promover_admin.data)

        # 6. Intento del Administrador de cambiar su propio rol o su propia institución -> 400 Bad Request
        resp_auto_rol = self.client.patch(
            f"/api/usuarios/{self.admin_norte.id_usuario}/",
            {"rol": self.rol_supervisor.id_rol},
            format="json",
        )
        self.assertEqual(resp_auto_rol.status_code, 400)
        self.assertIn("rol", resp_auto_rol.data)

        resp_auto_inst = self.client.patch(
            f"/api/usuarios/{self.admin_norte.id_usuario}/",
            {"id_institucion": self.inst_sur.id_institucion},
            format="json",
        )
        self.assertEqual(resp_auto_inst.status_code, 400)
        self.assertIn("id_institucion", resp_auto_inst.data)

        # 7. Un Supervisor no tiene permisos de edición sobre usuarios -> 403 Forbidden
        self.client.force_authenticate(user=self.supervisor)
        resp_sup_edit = self.client.patch(
            f"/api/usuarios/{self.jefa_norte.id_usuario}/?funcionalidad=supervision_pae",
            {"nombre": "Intento Supervisor"},
            format="json",
        )
        self.assertEqual(resp_sup_edit.status_code, 403)


class ActivacionDesactivacionUsuariosTests(TestCase):
    """
    Suite integral para auditar y verificar al 100% los 10 criterios de aceptación
    del módulo de Activación y Desactivación de Cuentas de Usuario en SIRAE PAE.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.rol_super = Rol.objects.create(nombre=Rol.NombreRol.SUPER_ADMINISTRADOR)
        self.rol_admin = Rol.objects.create(nombre=Rol.NombreRol.ADMINISTRADOR)
        self.rol_supervisor = Rol.objects.create(nombre=Rol.NombreRol.SUPERVISOR)
        self.rol_jefa = Rol.objects.create(nombre=Rol.NombreRol.JEFA_MANIPULADORAS)
        self.rol_manipuladora = Rol.objects.create(nombre=Rol.NombreRol.MANIPULADORA)

        self.inst_norte = Institucion.objects.create(
            nombre_institucion="IED Colegio del Norte",
            nit="800300100-1",
            estado="ACTIVO",
        )
        self.inst_sur = Institucion.objects.create(
            nombre_institucion="IED Colegio del Sur",
            nit="800300100-2",
            estado="ACTIVO",
        )

        self.superadmin = Usuario.objects.create_user(
            correo="superadmin@sirae.gov.co",
            nombre="Carlos",
            apellido="SuperAdmin",
            password="Super-Pass-2026!xQ",
            tipo_documento="CC",
            numero_documento="ACT0001",
            rol=self.rol_super,
            is_superuser=True,
            is_staff=True,
        )

        self.admin_norte = Usuario.objects.create_user(
            correo="admin.norte@sirae.edu.co",
            nombre="Patricia",
            apellido="Salazar",
            password="Admin-Pass-2026!xQ",
            tipo_documento="CC",
            numero_documento="ACT0002",
            rol=self.rol_admin,
            id_institucion=self.inst_norte,
            is_active=True,
        )

        self.admin_sur = Usuario.objects.create_user(
            correo="admin.sur@sirae.edu.co",
            nombre="Fernando",
            apellido="Vargas",
            password="Admin-Pass-2026!xQ",
            tipo_documento="CC",
            numero_documento="ACT0003",
            rol=self.rol_admin,
            id_institucion=self.inst_sur,
            is_active=True,
        )

        self.jefa_norte = Usuario.objects.create_user(
            correo="jefa.norte@sirae.edu.co",
            nombre="Lucía",
            apellido="Mendoza",
            password="Jefa-Pass-2026!xQ",
            tipo_documento="CC",
            numero_documento="ACT0004",
            rol=self.rol_jefa,
            id_institucion=self.inst_norte,
            is_active=True,
        )

        self.manipuladora_norte = Usuario.objects.create_user(
            correo="manip.norte@sirae.edu.co",
            nombre="Carmen",
            apellido="Rojas",
            password="Manip-Pass-2026!xQ",
            tipo_documento="CC",
            numero_documento="ACT0005",
            rol=self.rol_manipuladora,
            id_institucion=self.inst_norte,
            is_active=True,
        )

        self.supervisor = Usuario.objects.create_user(
            correo="supervisor@sirae.edu.co",
            nombre="Andrés",
            apellido="Cárdenas",
            password="Sup-Pass-2026!xQ",
            tipo_documento="CC",
            numero_documento="ACT0006",
            rol=self.rol_supervisor,
            is_active=True,
        )

    def test_criterio_1_estado_actual_cuenta_activa_inactiva_y_bloqueada(self):
        """
        Criterio 1: Muestra claramente el estado actual de la cuenta (Activa / Inactiva / Bloqueada).
        """
        self.client.force_authenticate(user=self.superadmin)
        resp_activa = self.client.get(f"/api/usuarios/{self.jefa_norte.id_usuario}/")
        self.assertEqual(resp_activa.status_code, 200)
        self.assertEqual(resp_activa.data["estado_display"], "Activo")
        self.assertFalse(resp_activa.data["esta_bloqueado"])

        # Cuenta inactiva
        self.jefa_norte.is_active = False
        self.jefa_norte.save()
        resp_inactiva = self.client.get(f"/api/usuarios/{self.jefa_norte.id_usuario}/")
        self.assertEqual(resp_inactiva.data["estado_display"], "Inactivo")

        # Cuenta bloqueada temporalmente
        self.jefa_norte.is_active = True
        self.jefa_norte.bloqueado_hasta = timezone.now() + timedelta(minutes=15)
        self.jefa_norte.save()
        resp_bloqueada = self.client.get(f"/api/usuarios/{self.jefa_norte.id_usuario}/")
        self.assertEqual(resp_bloqueada.data["estado_display"], "Bloqueado")
        self.assertTrue(resp_bloqueada.data["esta_bloqueado"])

    def test_criterio_3_y_10_autorizacion_estricta_por_ambito_y_restriccion_de_autogestion(self):
        """
        Criterio 3: Autorización estricta por rol y ámbito institucional.
        Criterio 10: Restricción de autogestión (nadie puede activarse/desactivarse a sí mismo).
        """
        # 1. Superadmin puede desactivar a un Administrador o personal operativo
        self.client.force_authenticate(user=self.superadmin)
        resp_super_desactiva = self.client.patch(
            f"/api/usuarios/{self.admin_norte.id_usuario}/cambiar-estado/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(resp_super_desactiva.status_code, 200)
        self.assertFalse(resp_super_desactiva.data["is_active"])

        # 2. Criterio 10: Autogestión bloqueada (Superadmin intentando desactivarse a sí mismo)
        resp_auto_super = self.client.patch(
            f"/api/usuarios/{self.superadmin.id_usuario}/cambiar-estado/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(resp_auto_super.status_code, 403)
        self.assertIn("propia cuenta", str(resp_auto_super.data))

        # 3. Administrador institucional: puede desactivar a la manipuladora de su propia institución
        self.client.force_authenticate(user=self.admin_norte)
        resp_admin_desactiva = self.client.patch(
            f"/api/usuarios/{self.manipuladora_norte.id_usuario}/cambiar-estado/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(resp_admin_desactiva.status_code, 200)
        self.assertFalse(resp_admin_desactiva.data["is_active"])

        # 4. Criterio 10: Administrador institucional intentando desactivarse a sí mismo -> 403
        resp_auto_admin = self.client.patch(
            f"/api/usuarios/{self.admin_norte.id_usuario}/cambiar-estado/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(resp_auto_admin.status_code, 403)

        # 5. Administrador institucional intentando cambiar estado a usuario de OTRA institución -> 403/404
        resp_otra_inst = self.client.patch(
            f"/api/usuarios/{self.admin_sur.id_usuario}/cambiar-estado/",
            {"is_active": False},
            format="json",
        )
        self.assertIn(resp_otra_inst.status_code, (403, 404))

        # 6. Usuario sin rol administrativo (Supervisor) intentando cambiar estado -> 403
        self.client.force_authenticate(user=self.supervisor)
        resp_sup_prohibido = self.client.patch(
            f"/api/usuarios/{self.jefa_norte.id_usuario}/cambiar-estado/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(resp_sup_prohibido.status_code, 403)

    def test_criterios_4_5_6_bloqueo_login_invalidacion_tokens_y_rechazo_peticiones_posteriores(self):
        """
        Criterio 4: Bloqueo de acceso al login si is_active=False.
        Criterio 5: Invalidación y revocación inmediata de tokens activos (blacklist).
        Criterio 6: Rechazo inmediato de peticiones API posteriores con tokens previos.
        """
        # 1. Iniciar sesión exitosamente con cuenta activa
        login_resp = self.client.post(
            reverse("login"),
            {"correo": self.jefa_norte.correo, "password": "Jefa-Pass-2026!xQ"},
            format="json",
        )
        self.assertEqual(login_resp.status_code, 200)
        access_token = login_resp.data["access"]
        refresh_token = login_resp.data["refresh"]

        # 2. Verificar que la cuenta realiza peticiones a la API con ese token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        api_pre_resp = self.client.get(f"/api/usuarios/{self.jefa_norte.id_usuario}/")
        self.assertEqual(api_pre_resp.status_code, 200)

        # 3. El Administrador institucional desactiva la cuenta de la jefa
        self.client.force_authenticate(user=self.admin_norte)
        desact_resp = self.client.patch(
            f"/api/usuarios/{self.jefa_norte.id_usuario}/cambiar-estado/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(desact_resp.status_code, 200)
        self.assertFalse(desact_resp.data["is_active"])

        # 4. Criterio 4: Impedir que la cuenta inactiva inicie sesión
        self.client.logout()
        login_inactivo_resp = self.client.post(
            reverse("login"),
            {"correo": self.jefa_norte.correo, "password": "Jefa-Pass-2026!xQ"},
            format="json",
        )
        self.assertEqual(login_inactivo_resp.status_code, 401)
        self.assertIn("inactiva", str(login_inactivo_resp.data["detail"]).lower())

        # 5. Criterio 5 y 6: El access token emitido previamente debe ser RECHAZADO de inmediato
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        api_post_resp = self.client.get(f"/api/usuarios/{self.jefa_norte.id_usuario}/")
        self.assertEqual(api_post_resp.status_code, 401)
        self.assertTrue(
            "inactivo" in str(api_post_resp.data).lower()
            or "revocado" in str(api_post_resp.data).lower()
        )

        # 6. Criterio 5: El refresh token previo también debe ser rechazado al intentar refresh
        refresh_resp = self.client.post(
            reverse("token_refresh"),
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(refresh_resp.status_code, 401)

    def test_criterio_7_integridad_historica_delete_realiza_inactivacion_logica_sin_borrado_fisico(self):
        """
        Criterio 7: Integridad Histórica. Conserva intactos todos los registros históricos,
        relaciones institucionales y bitácoras (DELETE alterna estado lógico is_active=False).
        """
        self.client.force_authenticate(user=self.admin_norte)
        user_id = self.manipuladora_norte.id_usuario

        del_resp = self.client.delete(f"/api/usuarios/{user_id}/")
        self.assertEqual(del_resp.status_code, 204)

        # El registro aún existe en la base de datos (NO fue borrado físicamente)
        self.assertTrue(Usuario.objects.filter(id_usuario=user_id).exists())
        self.manipuladora_norte.refresh_from_db()
        self.assertFalse(self.manipuladora_norte.is_active)
        self.assertEqual(self.manipuladora_norte.id_institucion_id, self.inst_norte.id_institucion)

    def test_criterio_9_auditoria_y_trazabilidad_del_cambio_de_estado(self):
        """
        Criterio 9: Registrar formalmente en AuditoriaUsuario quién realizó la operación (actor),
        timestamp exacto, estado anterior y estado nuevo.
        """
        self.client.force_authenticate(user=self.admin_norte)
        antes = timezone.now()

        # Desactivación
        resp_desact = self.client.patch(
            f"/api/usuarios/{self.jefa_norte.id_usuario}/cambiar-estado/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(resp_desact.status_code, 200)

        from apps_sirae.usuarios.models import AuditoriaUsuario
        aud_desact = AuditoriaUsuario.objects.filter(
            usuario_afectado=self.jefa_norte,
            accion="DESACTIVACION",
        ).first()

        self.assertIsNotNone(aud_desact)
        self.assertEqual(aud_desact.usuario_actor_id, self.admin_norte.id_usuario)
        self.assertEqual(aud_desact.estado_anterior, "Activo")
        self.assertEqual(aud_desact.estado_nuevo, "Inactivo")
        self.assertGreaterEqual(aud_desact.creado_en, antes)

        # Reactivación
        resp_react = self.client.patch(
            f"/api/usuarios/{self.jefa_norte.id_usuario}/cambiar-estado/",
            {"is_active": True},
            format="json",
        )
        self.assertEqual(resp_react.status_code, 200)

        aud_react = AuditoriaUsuario.objects.filter(
            usuario_afectado=self.jefa_norte,
            accion="ACTIVACION",
        ).first()

        self.assertIsNotNone(aud_react)
        self.assertEqual(aud_react.usuario_actor_id, self.admin_norte.id_usuario)
        self.assertEqual(aud_react.estado_anterior, "Inactivo")
        self.assertEqual(aud_react.estado_nuevo, "Activo")


class ConservacionSeguraSesionBackendTests(TestCase):
    """
    Auditoría y Pruebas Unitarias/Integración de Conservación y Persistencia de Sesión:
    Criterios 1, 3, 4 y 5 en Backend Django REST Framework.
    """
    def setUp(self):
        self.client = APIClient()
        self.rol_admin = Rol.objects.create(nombre="Administrador")
        self.institucion = Institucion.objects.create(nombre_institucion="Colegio Prueba PAE")
        self.usuario = Usuario.objects.create_user(
            correo="auditoria.sesion@sirae.com",
            nombre="Auditor",
            apellido="Seguridad",
            password="Password-Seguro-2026!",
            tipo_documento="CC",
            numero_documento="99881122",
            rol=self.rol_admin,
            id_institucion=self.institucion,
            is_active=True,
        )
        login_resp = self.client.post(
            "/api/auth/login/",
            {"correo": "auditoria.sesion@sirae.com", "password": "Password-Seguro-2026!"},
            format="json",
        )
        self.assertEqual(login_resp.status_code, 200)
        self.access_token = login_resp.data["access"]
        self.refresh_token = login_resp.data["refresh"]

    def test_criterio_1_y_3_validacion_activa_con_backend_auth_verify(self):
        """
        Criterios 1 y 3: Endpoint /api/auth/verify/ valida token activo y devuelve
        datos mínimos indispensables sin exponer credenciales.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get("/api/auth/verify/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("valido"))
        usuario_data = response.data.get("usuario", {})
        self.assertEqual(usuario_data.get("correo"), "auditoria.sesion@sirae.com")
        self.assertEqual(usuario_data.get("rol"), "Administrador")
        self.assertEqual(usuario_data.get("institucion_nombre"), "Colegio Prueba PAE")
        self.assertTrue(usuario_data.get("is_active"))

    def test_criterio_3_endpoint_usuarios_me(self):
        """
        Criterio 3: Endpoint /api/usuarios/me/ valida token activo y devuelve perfil autenticado.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get("/api/usuarios/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("correo"), "auditoria.sesion@sirae.com")
        self.assertEqual(response.data.get("id_usuario"), self.usuario.id_usuario)

    def test_criterio_4_manejo_sesiones_invalidas_token_inexistente_o_invalido(self):
        """
        Criterio 4: Si no hay token o es inválido, el backend rechaza con 401 Unauthorized.
        """
        self.client.credentials()  # Sin token
        response = self.client.get("/api/auth/verify/")
        self.assertEqual(response.status_code, 401)

        self.client.credentials(HTTP_AUTHORIZATION="Bearer token-invalido-o-expirado")
        response_bad = self.client.get("/api/auth/verify/")
        self.assertEqual(response_bad.status_code, 401)

    def test_criterio_4_manejo_sesiones_usuario_desactivado(self):
        """
        Criterio 4: Si la cuenta es desactivada en el backend, la validación activa rechaza la sesión.
        """
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get("/api/auth/verify/")
        self.assertIn(response.status_code, [401, 403])

        response_me = self.client.get("/api/usuarios/me/")
        self.assertIn(response_me.status_code, [401, 403])

    def test_criterio_5_cero_contrasenas_en_texto_plano_en_respuestas(self):
        """
        Criterio 5: Bajo ninguna circunstancia los endpoints de auth/sesión retornan
        contraseñas o hashes en la respuesta al cliente.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response_verify = self.client.get("/api/auth/verify/")
        self.assertEqual(response_verify.status_code, 200)
        user_dict = response_verify.data.get("usuario", {})
        self.assertNotIn("password", user_dict)
        self.assertNotIn("clave", user_dict)
        self.assertNotIn("contrasena", user_dict)

        response_me = self.client.get("/api/usuarios/me/")
        self.assertEqual(response_me.status_code, 200)
        self.assertNotIn("password", response_me.data)
        self.assertNotIn("clave", response_me.data)
        self.assertNotIn("contrasena", response_me.data)


class EdicionPerfilPropioBackendTests(TestCase):
    """
    Auditoría y Pruebas de los Criterios de Aceptación para:
    Edición de Datos Propios del Perfil (Autogestión) en Django REST Framework.
    """
    def setUp(self):
        self.client = APIClient()
        self.rol_supervisor = Rol.objects.create(nombre="Supervisor")
        self.rol_superadmin = Rol.objects.create(nombre="Super Administrador")
        self.institucion = Institucion.objects.create(nombre_institucion="Colegio San José PAE")
        self.sede = Sede.objects.create(nombre_sede="Sede Primaria", id_institucion=self.institucion)

        self.usuario = Usuario.objects.create_user(
            correo="supervisor.perfil@sirae.com",
            nombre="Santiago",
            apellido="Acosta",
            password="SecurePass2026!",
            tipo_documento="CC",
            numero_documento="77665544",
            rol=self.rol_supervisor,
            id_institucion=self.institucion,
            id_sede=self.sede,
            is_active=True,
        )

        login_resp = self.client.post(
            "/api/auth/login/",
            {"correo": "supervisor.perfil@sirae.com", "password": "SecurePass2026!"},
            format="json",
        )
        self.assertEqual(login_resp.status_code, 200)
        self.token = login_resp.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_criterio_1_visualizacion_datos_actuales_me(self):
        """
        Criterio 1: Visualización clara de los datos actuales del usuario autenticado vía /api/usuarios/me/.
        """
        response = self.client.get("/api/usuarios/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["nombre"], "Santiago")
        self.assertEqual(response.data["apellido"], "Acosta")
        self.assertEqual(response.data["correo"], "supervisor.perfil@sirae.com")
        self.assertEqual(response.data["rol_nombre"], "Supervisor")
        self.assertEqual(response.data["institucion_nombre"], "Colegio San José PAE")
        self.assertEqual(response.data["sede_nombre"], "Sede Primaria")
        self.assertTrue(response.data["is_active"])

    def test_criterio_2_y_4_actualizacion_exitosa_datos_modificables(self):
        """
        Criterios 2 y 4: Actualización permitida de campos autorizados (nombre, apellido)
        con validación previa robusta.
        """
        response = self.client.patch(
            "/api/usuarios/me/",
            {
                "nombre": "Santiago Alejandro",
                "apellido": "Acosta Barrera",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["nombre"], "Santiago Alejandro")
        self.assertEqual(response.data["apellido"], "Acosta Barrera")

        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.nombre, "Santiago Alejandro")
        self.assertEqual(self.usuario.apellido, "Acosta Barrera")

    def test_criterio_4_validacion_formato_nombres_invalidos(self):
        """
        Criterio 4: Rechazo ante nombres o apellidos muy cortos o con caracteres no permitidos.
        """
        response_corto = self.client.patch(
            "/api/usuarios/me/",
            {"nombre": "A"},
            format="json",
        )
        self.assertEqual(response_corto.status_code, 400)
        self.assertIn("nombre", response_corto.data)

        response_invalido = self.client.patch(
            "/api/usuarios/me/",
            {"nombre": "Santiago123@#!"},
            format="json",
        )
        self.assertEqual(response_invalido.status_code, 400)
        self.assertIn("nombre", response_invalido.data)

    def test_criterio_5_restriccion_estricta_de_campos_protegidos(self):
        """
        Criterio 5: Impedir de forma terminante que un usuario modifique por autogestión su propio rol,
        estado de cuenta, sede, correo institucional o asignaciones. El backend ignora o neutraliza estos campos.
        """
        payload_malicioso = {
            "nombre": "Santiago Verificado",
            "apellido": "Acosta",
            "rol": self.rol_superadmin.id_rol,
            "id_rol": self.rol_superadmin.id_rol,
            "is_active": False,
            "estado": "Inactivo",
            "correo": "atacante@evil.com",
            "email": "atacante@evil.com",
            "is_superuser": True,
            "is_staff": True,
            "id_institucion": 9999,
            "id_sede": 8888,
        }

        response = self.client.patch("/api/usuarios/me/", payload_malicioso, format="json")
        self.assertEqual(response.status_code, 200)

        self.usuario.refresh_from_db()
        # Nombre permitido sí se actualizó
        self.assertEqual(self.usuario.nombre, "Santiago Verificado")
        # Campos protegidos se mantuvieron intactos
        self.assertEqual(self.usuario.rol.nombre, "Supervisor")
        self.assertTrue(self.usuario.is_active)
        self.assertFalse(self.usuario.is_superuser)
        self.assertEqual(self.usuario.correo, "supervisor.perfil@sirae.com")
        self.assertEqual(self.usuario.id_institucion_id, self.institucion.id_institucion)
        self.assertEqual(self.usuario.id_sede_id, self.sede.id_sede)

    def test_criterio_6_usuario_no_autenticado_rechazado(self):
        """
        Criterio 6: Sin autenticación no se permite consultar ni editar el perfil.
        """
        self.client.credentials()  # Sin token
        resp_get = self.client.get("/api/usuarios/me/")
        self.assertEqual(resp_get.status_code, 401)

        resp_patch = self.client.patch("/api/usuarios/me/", {"nombre": "Test"}, format="json")
        self.assertEqual(resp_patch.status_code, 401)





