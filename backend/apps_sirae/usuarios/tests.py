from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.core.management import call_command
from django.contrib.auth.hashers import check_password
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps_sirae.usuarios.api.password_reset import PasswordResetService
from apps_sirae.usuarios.models import Usuario
from apps_sirae.roles.models import Rol


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
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_URL='https://frontend.example.com',
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

    def test_request_recovery_sends_link_to_configured_frontend(self):
        response = self.client.post(
            reverse('recuperar-password'),
            {'correo': self.usuario.correo},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        link = next(
            line for line in mail.outbox[0].body.splitlines()
            if line.startswith('https://frontend.example.com/recuperar-password?')
        )
        token = parse_qs(urlparse(link).query)['token'][0]
        self.assertIsNone(PasswordResetService.validar_token(token)[1])

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
        self.assertTrue(check_password('new-password-123', self.usuario.password))
        self.assertEqual(
            self.client.post(
                reverse('password-reset-validar-token'),
                {'token': token},
                format='json',
            ).status_code,
            400,
        )

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
        self.assertTrue(check_password('another-password-123', self.usuario.password))


class UsuarioLoginBehaviorTests(TestCase):
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

    def test_login_accepts_email_and_password(self):
        response = self.client.post(
            reverse("login"),
            {"correo": self.usuario.correo.upper(), "password": "Safe-Passphrase-2026!"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["usuario"]["correo"], self.usuario.correo)

    def test_login_rejects_wrong_password(self):
        response = self.client.post(
            reverse("login"),
            {"correo": self.usuario.correo, "password": "incorrect-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)


class UsuarioSeedCommandTests(TestCase):
    @patch("apps_sirae.usuarios.management.commands.crear_usuario_prueba.getpass.getpass")
    def test_seed_creates_accounts_and_does_not_reset_existing_passwords(self, get_password):
        get_password.return_value = "Unique-Safe-Passphrase-2026!"

        call_command("crear_usuario_prueba")

        self.assertEqual(Usuario.objects.count(), 4)
        self.assertEqual(get_password.call_count, 8)
        usuario = Usuario.objects.get(correo="admin@sirae.com")
        self.assertTrue(usuario.check_password("Unique-Safe-Passphrase-2026!"))

        call_command("crear_usuario_prueba")

        self.assertEqual(get_password.call_count, 8)
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password("Unique-Safe-Passphrase-2026!"))

    @patch("apps_sirae.usuarios.management.commands.crear_usuario_prueba.getpass.getpass")
    def test_seed_only_resets_existing_passwords_when_requested(self, get_password):
        Usuario.objects.create_user(
            correo="admin@sirae.com",
            nombre="Old",
            apellido="Admin",
            password="Previous-Safe-Passphrase-2026!",
            tipo_documento="CC",
            numero_documento="RESET001",
        )
        get_password.return_value = "Replacement-Safe-Passphrase-2026!"

        call_command("crear_usuario_prueba", "--reset-existing-passwords")

        usuario = Usuario.objects.get(correo="admin@sirae.com")
        self.assertTrue(usuario.check_password("Replacement-Safe-Passphrase-2026!"))
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
        self.role = Rol.objects.create(nombre=Rol.NombreRol.SUPERVISOR)
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
        self.assertEqual(
            response.data['usuario'],
            {
                'id_usuario': self.user.id_usuario,
                'nombre': 'Ana',
                'apellido': 'Pérez',
                'correo': 'supervisor@example.com',
                'numero_documento': '123456789',
                'rol': 'supervisor',
            },
        )

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
