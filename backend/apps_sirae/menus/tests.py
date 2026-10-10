from django.test import TestCase
from rest_framework.test import APIClient
from apps_sirae.jornadas.models import Jornada


class MenuApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        Jornada.objects.create(id_jornada=1, nombre_jornada='Jornada mañana')

    def autenticar(self, *, jefa=False, administrador=False, supervisor=False):
        self.client.force_authenticate(user=type(
            'UsuarioPrueba',
            (),
            {
                'is_authenticated': True,
                'es_jefa_manipuladoras': lambda self: jefa,
                'es_administrador': lambda self: administrador,
                'es_supervisor': lambda self: supervisor,
            },
        )())

    def test_jefa_can_register_menu(self):
        self.autenticar(jefa=True)

        response = self.client.post(
            '/api/menus/',
            {
                'id_jornada': 1,
                'fecha': '2026-10-10',
                'ninos_presentes': 24,
                'estado': 'ACTIVO',
                'informacion_nutricional': 'Menú balanceado',
                'id_contrato': 1,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['id_jornada'], 1)
        self.assertEqual(response.data['ninos_presentes'], 24)

    def test_supervisor_cannot_manage_menus(self):
        self.autenticar(supervisor=True)

        response = self.client.get('/api/menus/')

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_access_menus(self):
        response = self.client.get('/api/menus/')

        self.assertEqual(response.status_code, 401)
