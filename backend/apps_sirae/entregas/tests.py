from django.test import TestCase
from rest_framework.test import APIClient

from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.roles.models import Rol
from apps_sirae.tipos_mercado.models import TipoMercado
from apps_sirae.usuarios.models import Usuario
from .models import Entrega


class EntregaTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=type(
            'Supervisor',
            (),
            {
                'is_authenticated': True,
                'id_usuario': 17,
                'es_supervisor': lambda self: True,
                'es_administrador': lambda self: False,
            },
        )())
        self.ingrediente = Ingrediente.objects.create(nombre_ingrediente='Arroz')
        self.tipo_mercado = TipoMercado.objects.create(nombre_tipo='Granos')

    def test_create_delivery_saves_supervisor_and_returns_display_names(self):
        response = self.client.post(
            '/api/entregas/',
            {
                'id_ingrediente': self.ingrediente.id_ingrediente,
                'id_usuario_supervisor': 999,
                'id_tipo_mercado': self.tipo_mercado.id_tipo_mercado,
                'fecha_entrega': '2026-10-10',
                'fecha_vencimiento': '2026-11-10',
                'cantidad': '12.50',
                'observaciones': '',
                'frecuencia': 'Mensual',
                'unidad': 'Kg',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['id_usuario_supervisor'], 17)
        self.assertEqual(response.data['ingrediente_nombre'], 'Arroz')
        self.assertEqual(response.data['tipo_mercado_nombre'], 'Granos')
        self.assertEqual(response.data['frecuencia'], 'Mensual')
        self.assertEqual(response.data['unidad'], 'Kg')

    def test_unauthenticated_request_cannot_list_deliveries(self):
        self.client.force_authenticate(user=None)

        response = self.client.get('/api/entregas/')

        self.assertEqual(response.status_code, 401)

    def test_login_access_token_can_list_deliveries(self):
        self.client.force_authenticate(user=None)
        usuario = Usuario(
            correo='supervisor@example.com',
            nombre='Ana',
            apellido='Supervisora',
            tipo_documento='CC',
            numero_documento='12345678',
            rol=Rol.objects.create(nombre=Rol.NombreRol.SUPERVISOR),
        )
        usuario.set_password('clave-de-prueba-segura')
        usuario.save()

        login_response = self.client.post(
            '/api/auth/login/',
            {
                'correo': 'supervisor@example.com',
                'password': 'clave-de-prueba-segura',
            },
            format='json',
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertIn('access', login_response.data)
        self.assertIn('usuario', login_response.data)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )
        deliveries_response = self.client.get('/api/entregas/')

        self.assertEqual(deliveries_response.status_code, 200)
        self.assertEqual(deliveries_response.data, [])