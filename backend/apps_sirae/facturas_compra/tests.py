from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient

from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.roles.models import Rol
from apps_sirae.usuarios.models import Usuario
from .models import FacturaCompra, DetalleFacturaCompra, InventarioCentral


class FacturasCompraTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.rol_admin = Rol.objects.create(nombre=Rol.NombreRol.ADMINISTRADOR)
        self.admin = Usuario.objects.create(
            correo='admin@sirae.com',
            nombre='Admin',
            apellido='PAE',
            tipo_documento='CC',
            numero_documento='98765432',
            rol=self.rol_admin,
            is_staff=True,
        )
        self.admin.set_password('admin123')
        self.admin.save()
        self.client.force_authenticate(user=self.admin)

        self.unidad = UnidadMedida.objects.create(nombre='Kilogramo', abreviatura='kg')
        self.ingrediente = Ingrediente.objects.create(nombre_ingrediente='Frijol', id_unidad_medida=self.unidad)

    def test_crear_factura_suma_a_inventario_central(self):
        payload = {
            'numero_factura': 'FAC-001',
            'proveedor': 'Distribuidora Granos SAS',
            'fecha_compra': '2026-10-20',
            'detalles': [
                {
                    'id_ingrediente': self.ingrediente.id_ingrediente,
                    'cantidad': 150.0,
                    'precio_unitario': 4500.0,
                    'numero_lote': 'LOTE-123',
                    'fecha_vencimiento': '2027-01-01',
                }
            ]
        }

        response = self.client.post('/api/facturas-compra/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['numero_factura'], 'FAC-001')
        self.assertEqual(Decimal(str(response.data['valor_total'])), Decimal('675000.00'))

        inv_c = InventarioCentral.objects.get(id_ingrediente=self.ingrediente)
        self.assertEqual(inv_c.cantidad_disponible, Decimal('150.000'))

    def test_anular_factura_descuenta_inventario_central(self):
        # Crear factura inicial con 100 kg
        payload = {
            'numero_factura': 'FAC-002',
            'proveedor': 'Proveedor Central',
            'fecha_compra': '2026-10-20',
            'detalles': [
                {
                    'id_ingrediente': self.ingrediente.id_ingrediente,
                    'cantidad': 100.0,
                    'precio_unitario': 2000.0,
                }
            ]
        }
        res_create = self.client.post('/api/facturas-compra/', payload, format='json')
        self.assertEqual(res_create.status_code, 201)
        factura_id = res_create.data['id_factura']

        inv_c = InventarioCentral.objects.get(id_ingrediente=self.ingrediente)
        self.assertEqual(inv_c.cantidad_disponible, Decimal('100.000'))

        # Anular factura
        anular_payload = {
            'motivo_anulacion': 'Error en digitación del proveedor'
        }
        res_anular = self.client.post(f'/api/facturas-compra/{factura_id}/anular/', anular_payload, format='json')
        self.assertEqual(res_anular.status_code, 200)
        self.assertEqual(res_anular.data['factura']['estado'], 'ANULADA')

        # Verificar que el inventario central volvió a 0
        inv_c.refresh_from_db()
        self.assertEqual(inv_c.cantidad_disponible, Decimal('0.000'))

    def test_no_se_permite_eliminar_facturas(self):
        payload = {
            'numero_factura': 'FAC-003',
            'proveedor': 'Proveedor Test',
            'fecha_compra': '2026-10-20',
            'detalles': [
                {
                    'id_ingrediente': self.ingrediente.id_ingrediente,
                    'cantidad': 10.0,
                    'precio_unitario': 1000.0,
                }
            ]
        }
        res = self.client.post('/api/facturas-compra/', payload, format='json')
        factura_id = res.data['id_factura']

        # Intentar DELETE
        res_del = self.client.delete(f'/api/facturas-compra/{factura_id}/')
        self.assertEqual(res_del.status_code, 400)
        self.assertIn('Las facturas no pueden eliminarse', res_del.data['error'])
