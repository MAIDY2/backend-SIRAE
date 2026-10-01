from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps_sirae.usuarios.api.password_reset import PasswordResetService
from apps_sirae.usuarios.models import Usuario


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


@override_settings(GOOGLE_OAUTH2_CLIENT_ID='test-google-client-id')
class GoogleLoginTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.url = reverse('google-login')

	@patch('apps_sirae.usuarios.api.views.id_token.verify_oauth2_token')
	def test_new_user_requires_document_fields(self, verify_token):
		verify_token.return_value = {
			'email': 'new.user@example.com',
			'email_verified': True,
			'given_name': 'New',
			'family_name': 'User',
		}

		response = self.client.post(self.url, {'token': 'valid-token'}, format='json')

		self.assertEqual(response.status_code, 400)
		self.assertIn('tipo_documento', response.data)
		self.assertFalse(Usuario.objects.filter(correo='new.user@example.com').exists())

	@patch('apps_sirae.usuarios.api.views.id_token.verify_oauth2_token')
	def test_new_user_is_created_with_unusable_password(self, verify_token):
		verify_token.return_value = {
			'email': 'new.user@example.com',
			'email_verified': True,
			'given_name': 'New',
			'family_name': 'User',
		}

		response = self.client.post(
			self.url,
			{
				'token': 'valid-token',
				'tipo_documento': 'CC',
				'numero_documento': '123456',
			},
			format='json'
		)

		usuario = Usuario.objects.get(correo='new.user@example.com')
		self.assertEqual(response.status_code, 200)
		self.assertFalse(usuario.has_usable_password())
		verify_token.assert_called_once()
		self.assertEqual(verify_token.call_args.args[2], 'test-google-client-id')

	@patch('apps_sirae.usuarios.api.views.id_token.verify_oauth2_token')
	def test_unverified_email_is_rejected(self, verify_token):
		verify_token.return_value = {
			'email': 'unverified@example.com',
			'email_verified': False,
		}

		response = self.client.post(self.url, {'token': 'valid-token'}, format='json')

		self.assertEqual(response.status_code, 401)
		self.assertFalse(Usuario.objects.filter(correo='unverified@example.com').exists())

	@patch('apps_sirae.usuarios.api.views.id_token.verify_oauth2_token')
	def test_inactive_user_cannot_log_in(self, verify_token):
		Usuario.objects.create_user(
			correo='inactive@example.com',
			nombre='Inactive',
			apellido='User',
			password='local-password',
			tipo_documento='CC',
			numero_documento='654321',
			is_active=False,
		)
		verify_token.return_value = {
			'email': 'inactive@example.com',
			'email_verified': True,
		}

		response = self.client.post(self.url, {'token': 'valid-token'}, format='json')

		self.assertEqual(response.status_code, 403)
		self.assertNotIn('access', response.data)
