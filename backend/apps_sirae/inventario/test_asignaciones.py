from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.facturas_compra.models import InventarioCentral
from apps_sirae.grados.models import Grados, GrupoGramaje
from apps_sirae.gramage.models import Gramage
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.instituciones.models import Institucion, SupervisorInstitucion
from apps_sirae.inventario.models import AsignacionInventario, Inventario
from apps_sirae.jornadas.models import Jornada
from apps_sirae.reportes.services.plantillas_operativas import construir_datos_plantillas_operativas
from apps_sirae.roles.models import Rol
from apps_sirae.sede_jornada.models import SedeJornada, SedeJornadaGrado
from apps_sirae.sedes.models import Sede
from apps_sirae.tipos_mercado.models import TipoMercado
from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.usuarios.models import Usuario


class AsignacionInventarioFlujoTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.rol_super, _ = Rol.objects.get_or_create(nombre=Rol.NombreRol.SUPER_ADMINISTRADOR)
        self.rol_sup, _ = Rol.objects.get_or_create(nombre=Rol.NombreRol.SUPERVISOR)
        self.rol_adm, _ = Rol.objects.get_or_create(nombre=Rol.NombreRol.ADMINISTRADOR)

        self.inst_a = Institucion.objects.create(nombre_institucion='IE San José', nit='900100100')
        self.inst_b = Institucion.objects.create(nombre_institucion='IE Santa María', nit='900200200')

        self.sede_a1 = Sede.objects.create(
            id_institucion=self.inst_a,
            nombre_sede='Sede Principal',
            codigo_dane='11900100001',
            estado='ACTIVO',
        )
        self.sede_a2 = Sede.objects.create(
            id_institucion=self.inst_a,
            nombre_sede='Sede Norte',
            codigo_dane='11900100002',
            estado='ACTIVO',
        )
        self.sede_b1 = Sede.objects.create(
            id_institucion=self.inst_b,
            nombre_sede='Sede Sur',
            codigo_dane='11900100003',
            estado='ACTIVO',
        )

        self.superadmin = Usuario.objects.create_user(
            correo='sa@test.com',
            password='Password123*',
            nombre='Super',
            apellido='Admin',
            numero_documento='SA1001',
            rol=self.rol_super,
        )
        self.supervisor = Usuario.objects.create_user(
            correo='sup@test.com',
            password='Password123*',
            nombre='Carlos',
            apellido='Sup',
            numero_documento='SUP1001',
            rol=self.rol_sup,
        )
        SupervisorInstitucion.objects.create(id_supervisor=self.supervisor, id_institucion=self.inst_a)

        self.admin_a = Usuario.objects.create_user(
            correo='adm@test.com',
            password='Password123*',
            nombre='Ana',
            apellido='Admin',
            numero_documento='ADM1001',
            rol=self.rol_adm,
            id_institucion=self.inst_a,
        )

        self.u_kg, _ = UnidadMedida.objects.get_or_create(
            abreviatura='kg',
            defaults={'nombre': 'Kilogramo', 'tipo_magnitud': 'MASA', 'factor_conversion_base': Decimal('1000.000000')},
        )
        self.u_g, _ = UnidadMedida.objects.get_or_create(
            abreviatura='g',
            defaults={'nombre': 'Gramo', 'tipo_magnitud': 'MASA', 'factor_conversion_base': Decimal('1.000000')},
        )
        self.tm_no_per, _ = TipoMercado.objects.get_or_create(nombre_tipo='No Perecedero')

        self.arroz = Ingrediente.objects.create(
            nombre_ingrediente='Arroz Blanco',
            id_unidad_medida=self.u_kg,
            id_tipo_mercado=self.tm_no_per,
            tipo_conservacion='no_perecedero',
        )
        self.frijol = Ingrediente.objects.create(
            nombre_ingrediente='Fríjol Cargamanto',
            id_unidad_medida=self.u_kg,
            id_tipo_mercado=self.tm_no_per,
            tipo_conservacion='no_perecedero',
        )

        self.inv_c_arroz = InventarioCentral.objects.create(
            id_ingrediente=self.arroz,
            id_unidad_medida=self.u_kg,
            cantidad_disponible=Decimal('100.000'),
        )
        self.inv_c_frijol = InventarioCentral.objects.create(
            id_ingrediente=self.frijol,
            id_unidad_medida=self.u_kg,
            cantidad_disponible=Decimal('50.000'),
        )

        # Inventario global (sin institución/sede) que NO deben ver colegios
        Inventario.objects.create(
            id_ingrediente=self.arroz.id_ingrediente,
            cantidad_actual=Decimal('100.00'),
            stock_minimo=Decimal('0.00'),
            id_unidad_medida=self.u_kg.id_unidad_medida,
        )
        # Inventario físico de Sede A1
        Inventario.objects.create(
            id_ingrediente=self.arroz.id_ingrediente,
            id_institucion=self.inst_a,
            id_sede=self.sede_a1,
            cantidad_actual=Decimal('12.00'),
            stock_minimo=Decimal('2.00'),
            id_unidad_medida=self.u_kg.id_unidad_medida,
        )
        # Inventario físico de otra institución (Inst B)
        Inventario.objects.create(
            id_ingrediente=self.arroz.id_ingrediente,
            id_institucion=self.inst_b,
            id_sede=self.sede_b1,
            cantidad_actual=Decimal('40.00'),
            stock_minimo=Decimal('2.00'),
            id_unidad_medida=self.u_kg.id_unidad_medida,
        )

        # Configurar contrato institucional y cupos repartidos por el Admin en 2 sedes
        self.contrato = Contrato.objects.create(
            numero_cor='COR-INST-A',
            id_institucion=self.inst_a,
            id_usuario_supervisor=self.supervisor,
            estado='ACTIVO',
            cupos=100,
            periodicidad_perecederos='SEMANAL',
            dias_cobertura_perecederos=5,
            periodicidad_no_perecederos='MENSUAL',
            dias_cobertura_no_perecederos=20,
        )
        self.jornada = Jornada.objects.create(nombre_jornada='Mañana')
        self.grupo, _ = GrupoGramaje.objects.get_or_create(nombre='Primaria', defaults={'nivel_educativo': 'PRIMARIA'})
        self.grado = Grados.objects.create(
            nombre_grado='Primero',
            nivel_educativo='PRIMARIA',
            id_grupo_gramaje=self.grupo,
            estado='ACTIVO',
        )

        sj1 = SedeJornada.objects.create(id_sede=self.sede_a1, id_jornada=self.jornada, cupos=60)
        SedeJornadaGrado.objects.create(id_sede_jornada=sj1, id_grado=self.grado, cupos=60, estado='ACTIVO')

        sj2 = SedeJornada.objects.create(id_sede=self.sede_a2, id_jornada=self.jornada, cupos=40)
        SedeJornadaGrado.objects.create(id_sede_jornada=sj2, id_grado=self.grado, cupos=40, estado='ACTIVO')

        # Gramaje Arroz: 50g por estudiante/día -> 60*50g*20d = 60kg (neto 48kg porque Sede A1 tiene 12kg),
        # Sede A2: 40*50g*20d = 40kg -> total neto institución = 88kg
        Gramage.objects.create(
            id_ingrediente=self.arroz,
            id_grado=self.grado,
            id_unidad_medida=self.u_g,
            cantidad_gramaje=Decimal('50.000'),
            estado='ACTIVO',
        )

    def test_superadmin_sugiere_y_asigna_por_institucion_sin_sobreasignar(self):
        self.client.force_authenticate(user=self.superadmin)

        # 1. Sugerencia consolidada de la institución (60kg - 12kg + 40kg = 88kg neto)
        resp_sug = self.client.get(
            f'/api/asignaciones-inventario/sugerencia-institucion/?id_institucion={self.inst_a.id_institucion}&incluir_todos_gramajes=1'
        )
        self.assertEqual(resp_sug.status_code, 200)
        self.assertEqual(resp_sug.data['total_sedes_activas'], 2)
        self.assertEqual(resp_sug.data['total_cupos_sedes'], 100)
        arroz_sug = next(p for p in resp_sug.data['productos_sugeridos'] if p['id_ingrediente'] == self.arroz.id_ingrediente)
        self.assertEqual(arroz_sug['necesidad_neta_sedes'], 88.0)
        self.assertEqual(arroz_sug['sugerido_asignar'], 88.0)

        # 2. SuperAdmin asigna 70 kg a Institución A
        resp_asig = self.client.post(
            '/api/asignaciones-inventario/asignar-lote/',
            {
                'id_institucion': self.inst_a.id_institucion,
                'items': [{'id_ingrediente': self.arroz.id_ingrediente, 'cantidad': 70}],
            },
            format='json',
        )
        self.assertEqual(resp_asig.status_code, 201)

        # InventarioCentral físico sigue en 100, pero saldo libre para asignar bajó a 30
        resp_ic = self.client.get('/api/inventario-central/')
        self.assertEqual(resp_ic.status_code, 200)
        items_ic = resp_ic.data.get('results', resp_ic.data)
        arroz_ic = next(i for i in items_ic if i['id_ingrediente'] == self.arroz.id_ingrediente)
        self.assertEqual(Decimal(str(arroz_ic['cantidad_disponible'])), Decimal('100.000'))
        self.assertEqual(arroz_ic['cantidad_asignada_pendiente'], 70.0)
        self.assertEqual(arroz_ic['saldo_libre_asignar'], 30.0)

        # 3. Intentar asignar 40 kg a Institución B debe fallar (solo quedan 30 libres)
        resp_over = self.client.post(
            '/api/asignaciones-inventario/asignar-lote/',
            {
                'id_institucion': self.inst_b.id_institucion,
                'items': [{'id_ingrediente': self.arroz.id_ingrediente, 'cantidad': 40}],
            },
            format='json',
        )
        self.assertEqual(resp_over.status_code, 400)

        # 4. Anular la asignación libera los 70 kg
        asig_id = resp_asig.data['asignaciones'][0]['id_asignacion']
        resp_anular = self.client.post(f'/api/asignaciones-inventario/{asig_id}/anular/', {'motivo': 'Ajuste'}, format='json')
        self.assertEqual(resp_anular.status_code, 200)
        self.assertEqual(resp_anular.data['estado'], 'ANULADA')

        resp_ic2 = self.client.get('/api/inventario-central/')
        items_ic2 = resp_ic2.data.get('results', resp_ic2.data)
        arroz_ic2 = next(i for i in items_ic2 if i['id_ingrediente'] == self.arroz.id_ingrediente)
        self.assertEqual(arroz_ic2['saldo_libre_asignar'], 100.0)

    def test_supervisor_despacha_contra_asignacion_fifo_y_planillas_lo_muestran(self):
        # SuperAdmin asigna 70 kg de Arroz a Institución A
        self.client.force_authenticate(user=self.superadmin)
        self.client.post(
            '/api/asignaciones-inventario/asignar-lote/',
            {
                'id_institucion': self.inst_a.id_institucion,
                'items': [{'id_ingrediente': self.arroz.id_ingrediente, 'cantidad': 70}],
            },
            format='json',
        )

        # Supervisor consulta calcular-mercado de Sede A1: ve saldo asignado institucional = 70
        self.client.force_authenticate(user=self.supervisor)
        resp_calc = self.client.get(
            f'/api/entregas/calcular-mercado/?id_sede={self.sede_a1.id_sede}&incluir_todos_gramajes=1'
        )
        self.assertEqual(resp_calc.status_code, 200)
        self.assertTrue(resp_calc.data['tiene_asignaciones_institucion'])
        arroz_calc = next(p for p in resp_calc.data['productos_sugeridos'] if p['id_ingrediente'] == self.arroz.id_ingrediente)
        self.assertEqual(arroz_calc['cantidad_asignada_institucion'], 70.0)
        self.assertEqual(arroz_calc['saldo_asignado_institucion'], 70.0)

        # Despachar Fríjol (que NO fue asignado a Inst A) debe bloquearse porque la institución opera con asignaciones
        resp_no_asig = self.client.post(
            '/api/entregas/despacho-lote/',
            {
                'id_sede': self.sede_a1.id_sede,
                'fecha_entrega': '2026-11-12',
                'fecha_vencimiento': '2026-12-12',
                'validar_contra_asignacion': True,
                'items': [{'id_ingrediente': self.frijol.id_ingrediente, 'cantidad': 5, 'unidad': 'Kg'}],
            },
            format='json',
        )
        self.assertEqual(resp_no_asig.status_code, 400)

        # Despachar 45 kg de Arroz a Sede A1 funciona y baja el pendiente asignado a 25 kg y central físico a 55 kg
        resp_desp1 = self.client.post(
            '/api/entregas/despacho-lote/',
            {
                'id_sede': self.sede_a1.id_sede,
                'fecha_entrega': '2026-11-12',
                'fecha_vencimiento': '2026-12-12',
                'items': [{'id_ingrediente': self.arroz.id_ingrediente, 'cantidad': 45, 'unidad': 'Kg'}],
            },
            format='json',
        )
        self.assertEqual(resp_desp1.status_code, 201)

        self.inv_c_arroz.refresh_from_db()
        self.assertEqual(self.inv_c_arroz.cantidad_disponible, Decimal('55.000'))
        asig = AsignacionInventario.objects.get(id_institucion=self.inst_a, id_ingrediente=self.arroz)
        self.assertEqual(asig.cantidad_despachada, Decimal('45.000'))
        self.assertEqual(asig.cantidad_pendiente, Decimal('25.000'))
        self.assertEqual(asig.estado, 'ACTIVA')

        # Intentar despachar 30 kg a Sede A2 (solo quedan 25 asignados) debe bloquearse
        resp_exceso_asig = self.client.post(
            '/api/entregas/despacho-lote/',
            {
                'id_sede': self.sede_a2.id_sede,
                'fecha_entrega': '2026-11-12',
                'fecha_vencimiento': '2026-12-12',
                'items': [{'id_ingrediente': self.arroz.id_ingrediente, 'cantidad': 30, 'unidad': 'Kg'}],
            },
            format='json',
        )
        self.assertEqual(resp_exceso_asig.status_code, 400)

        # Despachar 25 kg exactos a Sede A2 completa la asignación
        resp_desp2 = self.client.post(
            '/api/entregas/despacho-lote/',
            {
                'id_sede': self.sede_a2.id_sede,
                'fecha_entrega': '2026-11-12',
                'fecha_vencimiento': '2026-12-12',
                'items': [{'id_ingrediente': self.arroz.id_ingrediente, 'cantidad': 25, 'unidad': 'Kg'}],
            },
            format='json',
        )
        self.assertEqual(resp_desp2.status_code, 201)
        asig.refresh_from_db()
        self.assertEqual(asig.cantidad_despachada, Decimal('70.000'))
        self.assertEqual(asig.estado, 'COMPLETADA')

        # Verificar que en plantillas_operativas aparece tanto `programado` (fix productos_sugeridos)
        # como `asignadoInstitucion` y `tieneAsignacion`
        planilla = construir_datos_plantillas_operativas(
            self.supervisor,
            {
                'id_institucion': self.inst_a.id_institucion,
                'id_sede': self.sede_a1.id_sede,
                'fecha_inicio': '2026-11-01',
                'fecha_fin': '2026-11-28',
            },
        )
        self.assertTrue(planilla['tiene_asignacion_institucion'])
        fila_arroz = next(
            row for row in planilla['remision']['no_perecederos']
            if row['id_ingrediente'] == self.arroz.id_ingrediente
        )
        self.assertGreater(fila_arroz['programado'], 0.0)
        self.assertTrue(fila_arroz['tieneAsignacion'])
        self.assertEqual(fila_arroz['asignadoInstitucion'], 70.0)
        self.assertEqual(fila_arroz['despachado'], 45.0)

    def test_inventario_api_filtra_estrictamente_por_institucion_y_sede(self):
        # El Admin de Institución A solo debe ver su sede_a1 (12 kg), nunca el global (100 kg) ni Institución B (40 kg)
        self.client.force_authenticate(user=self.admin_a)
        resp = self.client.get('/api/inventario/')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data.get('results', resp.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id_sede'], self.sede_a1.id_sede)
        self.assertEqual(Decimal(str(rows[0]['cantidad_actual'])), Decimal('12.00'))

        # Admin tampoco puede consultar resúmenes de asignaciones de otra institución
        resp_ajena = self.client.get(
            f'/api/asignaciones-inventario/resumen-institucion/?id_institucion={self.inst_b.id_institucion}'
        )
        self.assertEqual(resp_ajena.status_code, 403)

