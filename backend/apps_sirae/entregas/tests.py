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

    def test_calcular_mercado_returns_correct_calculations(self):
        from apps_sirae.instituciones.models import Institucion
        from apps_sirae.sedes.models import Sede
        from apps_sirae.jornadas.models import Jornada
        from apps_sirae.sede_jornada.models import SedeJornada
        from apps_sirae.gramage.models import Gramage
        from apps_sirae.facturas_compra.models import InventarioCentral
        from decimal import Decimal

        inst = Institucion.objects.create(nombre_institucion="Colegio Prueba")
        sede = Sede.objects.create(id_institucion=inst, nombre_sede="Sede Central")
        jornada = Jornada.objects.create(nombre_jornada="Mañana")
        SedeJornada.objects.create(id_sede=sede, id_jornada=jornada, cupos=50)

        Gramage.objects.create(
            id_ingrediente=self.ingrediente,
            cantidad_gramaje=Decimal('0.100'),
            descripcion='Porción de arroz 100g'
        )

        InventarioCentral.objects.create(
            id_ingrediente=self.ingrediente,
            cantidad_disponible=Decimal('200.000'),
            stock_minimo=Decimal('10.000')
        )

        # 50 cupos * 0.100 kg * 10 días = 50.0 kg consumo teórico
        response = self.client.get(f'/api/entregas/calcular-mercado/?id_sede={sede.id_sede}&dias=10')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id_sede'], sede.id_sede)
        self.assertEqual(response.data['total_cupos'], 50)
        self.assertEqual(response.data['dias_calculados'], 10)
        self.assertEqual(len(response.data['productos_sugeridos']), 1)

        prod = response.data['productos_sugeridos'][0]
        self.assertEqual(prod['id_ingrediente'], self.ingrediente.id_ingrediente)
        self.assertEqual(prod['consumo_teorico_periodo'], 50.0)
        self.assertEqual(prod['cantidad_sugerida_despacho'], 50.0)
        self.assertEqual(prod['stock_bodega_central'], 200.0)
        self.assertEqual(prod['estado_bodega_central'], 'SUFICIENTE')

    def test_despacho_lote_creates_deliveries_and_updates_inventories(self):
        from apps_sirae.instituciones.models import Institucion
        from apps_sirae.sedes.models import Sede
        from apps_sirae.facturas_compra.models import InventarioCentral
        from apps_sirae.inventario.models import Inventario
        from decimal import Decimal

        inst = Institucion.objects.create(nombre_institucion="Colegio Prueba 2")
        sede = Sede.objects.create(id_institucion=inst, nombre_sede="Sede Norte")

        inv_c = InventarioCentral.objects.create(
            id_ingrediente=self.ingrediente,
            cantidad_disponible=Decimal('100.000')
        )

        payload = {
            'id_sede': sede.id_sede,
            'id_tipo_mercado': self.tipo_mercado.id_tipo_mercado,
            'fecha_entrega': '2026-10-20',
            'fecha_vencimiento': '2026-11-20',
            'observaciones': 'Despacho quincenal',
            'frecuencia': 'Quincenal',
            'items': [
                {
                    'id_ingrediente': self.ingrediente.id_ingrediente,
                    'cantidad': 30.0,
                    'unidad': 'Kg'
                }
            ]
        }

        response = self.client.post('/api/entregas/despacho-lote/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['total_items'], 1)

        # Verificar que el InventarioCentral se redujo de 100 a 70
        inv_c.refresh_from_db()
        self.assertEqual(inv_c.cantidad_disponible, Decimal('70.000'))

        # Verificar que el Inventario de la sede tiene 30
        inv_sede = Inventario.objects.get(id_sede=sede, id_ingrediente=self.ingrediente.id_ingrediente)
        self.assertEqual(inv_sede.cantidad_actual, Decimal('30.000'))