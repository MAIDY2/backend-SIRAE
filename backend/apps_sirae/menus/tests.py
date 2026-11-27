from django.test import TestCase
from rest_framework.test import APIClient
from apps_sirae.jornadas.models import Jornada
from apps_sirae.menus.models import Menu


class MenuApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        Jornada.objects.get_or_create(id_jornada=1, defaults={'nombre_jornada': 'Jornada mañana'})

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

    def test_supervisor_can_list_and_approve_or_reject_menus(self):
        menu = Menu.objects.create(
            id_jornada_id=1,
            fecha='2026-10-10',
            ninos_presentes=30,
            estado='PENDIENTE',
            informacion_nutricional='Menú inicial',
            id_contrato=1,
        )
        self.autenticar(supervisor=True)

        get_res = self.client.get('/api/menus/')
        self.assertEqual(get_res.status_code, 200)

        patch_res = self.client.patch(
            f'/api/menus/{menu.id_menu}/',
            {'estado': 'APROBADO'},
            format='json',
        )
        self.assertEqual(patch_res.status_code, 200, patch_res.data)
        self.assertEqual(patch_res.data['estado'], 'APROBADO')

        put_res = self.client.put(
            f'/api/menus/{menu.id_menu}/',
            {
                'id_jornada': 1,
                'fecha': '2026-10-10',
                'ninos_presentes': 30,
                'estado': 'RECHAZADO',
                'informacion_nutricional': 'Menú inicial',
                'id_contrato': 1,
            },
            format='json',
        )
        self.assertEqual(put_res.status_code, 200, put_res.data)
        self.assertEqual(put_res.data['estado'], 'RECHAZADO')

    def test_unauthenticated_user_cannot_access_menus(self):
        response = self.client.get('/api/menus/')

        self.assertEqual(response.status_code, 401)
