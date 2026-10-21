from django.test import TestCase
from rest_framework.test import APIClient


class AsistenciaDiariaTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def autenticar(self, *, jefa=False, administrador=False, supervisor=False):
        self.client.force_authenticate(user=type(
            'UsuarioPrueba',
            (),
            {
                'is_authenticated': True,
                'id_usuario': 19,
                'es_jefa_manipuladoras': lambda self: jefa,
                'es_administrador': lambda self: administrador,
                'es_supervisor': lambda self: supervisor,
            },
        )())

    def test_only_jefa_can_register_daily_attendance(self):
        self.autenticar(jefa=True)

        response = self.client.post(
            '/api/asistencia-diaria/',
            {
                'id_grado': 3,
                'fecha': '2026-10-10',
                'ninos_presentes': 24,
                'id_usuario_manipuladora': 999,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['id_grado'], 3)
        self.assertEqual(response.data['ninos_presentes'], 24)
        self.assertEqual(response.data['id_usuario_manipuladora'], 19)

    def test_supervisor_cannot_access_daily_attendance(self):
        self.autenticar(supervisor=True)

        response = self.client.get('/api/asistencia-diaria/')

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_access_daily_attendance(self):
        response = self.client.get('/api/asistencia-diaria/')

        self.assertEqual(response.status_code, 401)