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
        items = deliveries_response.data.get('results', deliveries_response.data) if isinstance(deliveries_response.data, dict) else deliveries_response.data
        self.assertEqual(items, [])

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
        self.assertFalse(
            Inventario.objects.filter(
                id_sede=sede,
                id_ingrediente=self.ingrediente.id_ingrediente
            ).exists()
        )

    def test_confirm_reception_adds_to_institution_inventory(self):
        from decimal import Decimal
        from apps_sirae.instituciones.models import Institucion
        from apps_sirae.inventario.models import Inventario

        institucion = Institucion.objects.create(
            nombre_institucion='Institución receptora',
            nit='900123456'
        )
        otra_institucion = Institucion.objects.create(
            nombre_institucion='Otra institución',
            nit='900654321'
        )
        Inventario.objects.create(
            id_ingrediente=self.ingrediente.id_ingrediente,
            id_institucion=institucion,
            cantidad_actual=Decimal('15.00'),
            stock_minimo=Decimal('0.00'),
            id_unidad_medida=1
        )
        Inventario.objects.create(
            id_ingrediente=self.ingrediente.id_ingrediente,
            id_institucion=otra_institucion,
            cantidad_actual=Decimal('40.00'),
            stock_minimo=Decimal('0.00'),
            id_unidad_medida=1
        )
        entrega = Entrega.objects.create(
            id_institucion=institucion,
            id_ingrediente=self.ingrediente.id_ingrediente,
            id_usuario_supervisor=17,
            id_tipo_mercado=self.tipo_mercado.id_tipo_mercado,
            fecha_entrega='2026-11-08',
            fecha_vencimiento='2027-02-06',
            cantidad=Decimal('10.00'),
            estado='EN_TRANSITO'
        )
        administrador = Usuario.objects.create(
            correo='admin-recepcion@example.com',
            nombre='Admin',
            apellido='Receptor',
            tipo_documento='CC',
            numero_documento='987654321',
            rol=Rol.objects.create(nombre=Rol.NombreRol.ADMINISTRADOR),
            id_institucion=institucion
        )
        self.client.force_authenticate(user=administrador)

        response = self.client.post(
            f'/api/entregas/{entrega.id_entrega}/confirmar-recepcion/',
            {
                'cantidad_recibida': '8.00',
                'cantidad_rechazada': '2.00',
                'motivo_rechazo': 'Producto dañado',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Inventario.objects.get(
                id_ingrediente=self.ingrediente.id_ingrediente,
                id_institucion=institucion,
                id_sede__isnull=True
            ).cantidad_actual,
            Decimal('23.00')
        )
        self.assertEqual(
            Inventario.objects.get(
                id_ingrediente=self.ingrediente.id_ingrediente,
                id_institucion=otra_institucion,
                id_sede__isnull=True
            ).cantidad_actual,
            Decimal('40.00')
        )

    def test_confirm_legacy_precredited_delivery_only_removes_rejected_amount(self):
        from decimal import Decimal
        from apps_sirae.instituciones.models import Institucion
        from apps_sirae.inventario.models import Inventario

        institucion = Institucion.objects.create(
            nombre_institucion='Institución histórica',
            nit='900111222'
        )
        Inventario.objects.create(
            id_ingrediente=self.ingrediente.id_ingrediente,
            id_institucion=institucion,
            cantidad_actual=Decimal('25.00'),
            stock_minimo=Decimal('0.00'),
            id_unidad_medida=1
        )
        entrega = Entrega.objects.create(
            id_institucion=institucion,
            id_ingrediente=self.ingrediente.id_ingrediente,
            id_usuario_supervisor=17,
            id_tipo_mercado=self.tipo_mercado.id_tipo_mercado,
            fecha_entrega='2026-11-08',
            fecha_vencimiento='2027-02-06',
            cantidad=Decimal('10.00'),
            estado='EN_TRANSITO',
            inventario_preacreditado=True
        )
        administrador = Usuario.objects.create(
            correo='admin-historico@example.com',
            nombre='Admin',
            apellido='Receptor',
            tipo_documento='CC',
            numero_documento='987654322',
            rol=Rol.objects.create(nombre=Rol.NombreRol.ADMINISTRADOR),
            id_institucion=institucion
        )
        self.client.force_authenticate(user=administrador)

        response = self.client.post(
            f'/api/entregas/{entrega.id_entrega}/confirmar-recepcion/',
            {
                'cantidad_recibida': '8.00',
                'cantidad_rechazada': '2.00',
                'motivo_rechazo': 'Producto dañado',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Inventario.objects.get(
                id_ingrediente=self.ingrediente.id_ingrediente,
                id_institucion=institucion,
                id_sede__isnull=True
            ).cantidad_actual,
            Decimal('23.00')
        )


class CalculoAbastecimientoDespachoHU5TestCase(TestCase):
    """Pruebas unitarias e integración para HU 5: cálculo automático por sede y soporte auditable."""

    def setUp(self):
        from apps_sirae.contratos_pae.models import Contrato
        from apps_sirae.facturas_compra.models import InventarioCentral
        from apps_sirae.grados.models import Grados, GrupoGramaje
        from apps_sirae.gramage.models import Gramage
        from apps_sirae.instituciones.models import Institucion, SupervisorInstitucion
        from apps_sirae.jornadas.models import Jornada
        from apps_sirae.sede_jornada.models import SedeJornada, SedeJornadaGrado
        from apps_sirae.sedes.models import Sede
        from apps_sirae.unidades_medida.models import UnidadMedida

        self.client = APIClient()
        self.rol_supervisor = Rol.objects.create(nombre=Rol.NombreRol.SUPERVISOR)
        self.supervisor = Usuario.objects.create(
            correo='sup-hu5@example.com',
            nombre='Carlos',
            apellido='Supervisor',
            tipo_documento='CC',
            numero_documento='100200300',
            rol=self.rol_supervisor,
        )
        self.supervisor.set_password('ClaveSegura123!')
        self.supervisor.save()

        self.institucion = Institucion.objects.create(nombre_institucion='IE Simón Bolívar', nit='900100001')
        self.institucion_ajena = Institucion.objects.create(nombre_institucion='IE Externa', nit='900100002')
        SupervisorInstitucion.objects.create(
            id_supervisor=self.supervisor,
            id_institucion=self.institucion,
        )

        self.sede = Sede.objects.create(
            id_institucion=self.institucion,
            nombre_sede='Sede Principal',
            estado='ACTIVO',
        )
        self.sede_ajena = Sede.objects.create(
            id_institucion=self.institucion_ajena,
            nombre_sede='Sede Ajena',
            estado='ACTIVO',
        )
        self.jornada = Jornada.objects.create(nombre_jornada='Mañana')

        self.u_g = UnidadMedida.objects.create(
            nombre='Gramo', abreviatura='g', tipo_magnitud='MASA', factor_conversion_base='1'
        )
        self.u_kg = UnidadMedida.objects.create(
            nombre='Kilogramo', abreviatura='Kg', tipo_magnitud='MASA', factor_conversion_base='1000'
        )
        self.u_ml = UnidadMedida.objects.create(
            nombre='Mililitro', abreviatura='ml', tipo_magnitud='VOLUMEN', factor_conversion_base='1'
        )
        self.u_l = UnidadMedida.objects.create(
            nombre='Litro', abreviatura='L', tipo_magnitud='VOLUMEN', factor_conversion_base='1000'
        )
        self.u_und = UnidadMedida.objects.create(
            nombre='Unidad', abreviatura='Und', tipo_magnitud='UNIDAD', factor_conversion_base='1'
        )

        self.tm_no_per = TipoMercado.objects.create(nombre_tipo='No perecedero')
        self.tm_per = TipoMercado.objects.create(nombre_tipo='Perecedero')

        self.arroz = Ingrediente.objects.create(
            nombre_ingrediente='Arroz',
            id_unidad_medida=self.u_kg,
            tipo_conservacion='no_perecedero',
            id_tipo_mercado=self.tm_no_per,
        )
        self.leche = Ingrediente.objects.create(
            nombre_ingrediente='Leche líquida',
            id_unidad_medida=self.u_l,
            tipo_conservacion='perecedero',
            id_tipo_mercado=self.tm_per,
        )

        self.grupo_inf = GrupoGramaje.objects.create(nombre='Preescolar', nivel_educativo='PREESCOLAR')
        self.grupo_sec = GrupoGramaje.objects.create(nombre='Secundaria', nivel_educativo='SECUNDARIA')
        self.grado_pre = Grados.objects.create(
            nombre_grado='Transición', id_grupo_gramaje=self.grupo_inf, nivel_educativo='PREESCOLAR'
        )
        self.grado_sec = Grados.objects.create(
            nombre_grado='Sexto', id_grupo_gramaje=self.grupo_sec, nivel_educativo='SECUNDARIA'
        )

        self.sj = SedeJornada.objects.create(id_sede=self.sede, id_jornada=self.jornada, cupos=50)
        self.sj_pre = SedeJornadaGrado.objects.create(
            id_sede_jornada=self.sj, id_grado=self.grado_pre, cupos=20, estado='ACTIVO'
        )
        self.sj_sec = SedeJornadaGrado.objects.create(
            id_sede_jornada=self.sj, id_grado=self.grado_sec, cupos=30, estado='ACTIVO'
        )

        self.contrato = Contrato.objects.create(
            numero_cor='CTR-2026-001',
            estado='Activo',
            id_institucion=self.institucion,
            id_sede=self.sede,
            id_jornada=self.jornada,
            id_usuario_supervisor=self.supervisor,
            cupos=50,
            periodicidad_perecederos='SEMANAL',
            dias_cobertura_perecederos=5,
            periodicidad_no_perecederos='MENSUAL',
            dias_cobertura_no_perecederos=20,
        )

        # Gramajes: Arroz 50g Preescolar / 100g Sexto; Leche 200ml Preescolar (falta en Sexto intencional en un test)
        self.g_arroz_pre = Gramage.objects.create(
            id_ingrediente=self.arroz,
            id_grado=self.grado_pre,
            id_unidad_medida=self.u_g,
            cantidad_gramaje='50.000',
            estado='ACTIVO',
        )
        self.g_arroz_sec = Gramage.objects.create(
            id_ingrediente=self.arroz,
            id_grado=self.grado_sec,
            id_unidad_medida=self.u_g,
            cantidad_gramaje='100.000',
            estado='ACTIVO',
        )
        self.g_leche_pre = Gramage.objects.create(
            id_ingrediente=self.leche,
            id_grado=self.grado_pre,
            id_unidad_medida=self.u_ml,
            cantidad_gramaje='200.000',
            estado='ACTIVO',
        )
        self.g_leche_sec = Gramage.objects.create(
            id_ingrediente=self.leche,
            id_grado=self.grado_sec,
            id_unidad_medida=self.u_ml,
            cantidad_gramaje='250.000',
            estado='ACTIVO',
        )

        self.inv_central_arroz = InventarioCentral.objects.create(
            id_ingrediente=self.arroz, cantidad_disponible='50.000', stock_minimo='5.000'
        )
        self.inv_central_leche = InventarioCentral.objects.create(
            id_ingrediente=self.leche, cantidad_disponible='100.000', stock_minimo='5.000'
        )

    def _crear_menu_con_receta(self, ingredientes):
        from apps_sirae.detalle_plato.models import DetallePlato
        from apps_sirae.menus.models import Menu
        from apps_sirae.platos.models import Plato
        from apps_sirae.receta_componente.models import RecetaComponente

        menu = Menu.objects.create(
            id_jornada=self.jornada,
            fecha='2026-11-11',
            ninos_presentes=50,
            estado='ACTIVO',
            informacion_nutricional='Ciclo 1',
            id_contrato=self.contrato.id_contrato,
        )
        plato = Plato.objects.create(nombre_plato='Almuerzo Estándar', componente='Principal')
        DetallePlato.objects.create(id_menu=menu.id_menu, id_plato=plato, porcion_por_nino='100.00')
        for ing in ingredientes:
            RecetaComponente.objects.create(
                id_plato=plato,
                id_ingrediente=ing,
                cantidad='100.00',
                base_cantidad='POR_NINO',
            )

    def test_supervisor_solo_puede_consultar_sede_asignada(self):
        self.client.force_authenticate(user=self.supervisor)
        resp_ajena = self.client.get(f'/api/entregas/calcular-mercado/?id_sede={self.sede_ajena.id_sede}')
        self.assertEqual(resp_ajena.status_code, 403)

        resp_propia = self.client.get(f'/api/entregas/calcular-mercado/?id_sede={self.sede.id_sede}')
        self.assertEqual(resp_propia.status_code, 200)

    def test_calculo_consolida_grados_convierte_unidades_y_diferencia_perecederos(self):
        from decimal import Decimal
        from apps_sirae.inventario.models import Inventario

        self._crear_menu_con_receta([self.arroz, self.leche])
        # Stock actual en sede: 10 Kg de Arroz -> neto Arroz debe restar 10 Kg
        Inventario.objects.create(
            id_ingrediente=self.arroz.id_ingrediente,
            id_institucion=self.institucion,
            id_sede=self.sede,
            cantidad_actual=Decimal('10.00'),
            stock_minimo=Decimal('0.00'),
            id_unidad_medida=self.u_kg.id_unidad_medida,
        )

        self.client.force_authenticate(user=self.supervisor)
        resp = self.client.get(f'/api/entregas/calcular-mercado/?id_sede={self.sede.id_sede}')
        self.assertEqual(resp.status_code, 200)

        data = resp.data
        self.assertFalse(data['impacta_inventario'])
        self.assertEqual(data['origen_productos'], 'MENUS_RECETAS')
        self.assertEqual(data['total_cupos'], 50)
        self.assertEqual(data['periodicidad']['dias_perecederos'], 5)
        self.assertEqual(data['periodicidad']['dias_no_perecederos'], 20)

        por_nombre = {p['nombre_ingrediente']: p for p in data['productos_sugeridos']}

        # Arroz (no perecedero -> 20 días):
        # Preescolar: 20 * 0.05 kg * 20 = 20 Kg
        # Sexto:      30 * 0.10 kg * 20 = 60 Kg -> Total requerido = 80 Kg
        # Stock sede = 10 Kg -> Neto sugerido = 70 Kg; Central = 50 Kg -> INSUFICIENTE, pendiente = 20 Kg
        arroz = por_nombre['Arroz']
        self.assertFalse(arroz['es_perecedero'])
        self.assertEqual(arroz['dias_periodo'], 20)
        self.assertEqual(arroz['cantidad_total_requerida'], 80.0)
        self.assertEqual(arroz['stock_actual_sede'], 10.0)
        self.assertEqual(arroz['cantidad_sugerida_despacho'], 70.0)
        self.assertEqual(arroz['stock_bodega_central'], 50.0)
        self.assertEqual(arroz['estado_bodega_central'], 'INSUFICIENTE')
        self.assertEqual(arroz['pendiente_abastecer'], 20.0)
        self.assertEqual(len(arroz['detalle_por_grado']), 2)

        # Leche (perecedero -> 5 días):
        # Preescolar: 20 * 0.20 L * 5 = 20 L
        # Sexto:      30 * 0.25 L * 5 = 37.5 L -> Total = 57.5 L; Central = 100 L -> SUFICIENTE
        leche = por_nombre['Leche líquida']
        self.assertTrue(leche['es_perecedero'])
        self.assertEqual(leche['dias_periodo'], 5)
        self.assertEqual(leche['cantidad_total_requerida'], 57.5)
        self.assertEqual(leche['estado_bodega_central'], 'SUFICIENTE')
        self.assertEqual(leche['pendiente_abastecer'], 0.0)

        # Verificar que calcular NO descontó inventario central ni de sede
        self.inv_central_arroz.refresh_from_db()
        self.inv_central_leche.refresh_from_db()
        self.assertEqual(self.inv_central_arroz.cantidad_disponible, Decimal('50.000'))
        self.assertEqual(self.inv_central_leche.cantidad_disponible, Decimal('100.000'))

    def test_reporta_faltantes_configuracion_gramaje_menu_y_conversion_invalida(self):
        from apps_sirae.gramage.models import Gramage

        # Sin menú programado debe advertir MENUS faltante
        self.client.force_authenticate(user=self.supervisor)
        resp_sin_menu = self.client.get(f'/api/entregas/calcular-mercado/?id_sede={self.sede.id_sede}')
        self.assertEqual(resp_sin_menu.status_code, 200)
        tipos_sin_menu = {f['tipo'] for f in resp_sin_menu.data['faltantes_configuracion']}
        self.assertIn('MENUS', tipos_sin_menu)

        # Eliminar gramaje de Sexto para Leche + crear producto con unidad incompatible (g -> Und)
        self.g_leche_sec.delete()
        huevos = Ingrediente.objects.create(
            nombre_ingrediente='Huevos',
            id_unidad_medida=self.u_und,
            tipo_conservacion='perecedero',
            id_tipo_mercado=self.tm_per,
        )
        Gramage.objects.create(
            id_ingrediente=huevos,
            id_grado=self.grado_pre,
            id_unidad_medida=self.u_g,
            cantidad_gramaje='60.000',
            estado='ACTIVO',
        )
        self._crear_menu_con_receta([self.leche, huevos])

        resp = self.client.get(f'/api/entregas/calcular-mercado/?id_sede={self.sede.id_sede}')
        self.assertEqual(resp.status_code, 200)
        tipos = {f['tipo'] for f in resp.data['faltantes_configuracion']}
        self.assertIn('GRAMAJES', tipos)
        self.assertIn('CONVERSION_UNIDAD', tipos)

        por_nombre = {p['nombre_ingrediente']: p for p in resp.data['productos_sugeridos']}
        # Leche no asume cantidad arbitraria para Sexto: solo suma Preescolar (20 * 0.2 * 5 = 20 L)
        self.assertEqual(por_nombre['Leche líquida']['cantidad_total_requerida'], 20.0)
        self.assertTrue(por_nombre['Leche líquida']['tiene_gramajes_faltantes'])
        self.assertEqual(por_nombre['Huevos']['estado_bodega_central'], 'ERROR_CONVERSION')

    def test_recalcula_al_cambiar_cupos_gramajes_o_dias(self):
        self._crear_menu_con_receta([self.arroz])
        self.client.force_authenticate(user=self.supervisor)

        r1 = self.client.get(f'/api/entregas/calcular-mercado/?id_sede={self.sede.id_sede}')
        self.assertEqual(r1.data['productos_sugeridos'][0]['cantidad_total_requerida'], 80.0)

        # Modificar cupos y gramaje antes de confirmar despacho
        self.sj_pre.cupos = 40
        self.sj_pre.save()
        self.g_arroz_pre.cantidad_gramaje = '100.000'
        self.g_arroz_pre.save()

        # Recalcula con 40*0.1*10 + 30*0.1*10 = 70 Kg para 10 días
        r2 = self.client.get(f'/api/entregas/calcular-mercado/?id_sede={self.sede.id_sede}&dias=10')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data['total_cupos'], 70)
        self.assertEqual(r2.data['productos_sugeridos'][0]['cantidad_total_requerida'], 70.0)

    def test_despacho_bloquea_exceso_sin_autorizacion_y_guarda_snapshot_auditable(self):
        from decimal import Decimal
        from apps_sirae.entregas.models import CalculoEntrega

        self._crear_menu_con_receta([self.leche])  # Leche requerida: 57.5 L
        self.client.force_authenticate(user=self.supervisor)

        # 1. Intentar despachar 70 L (> 57.5 L) SIN autorización/justificación -> bloqueado (400)
        resp_bloqueado = self.client.post(
            '/api/entregas/despacho-lote/',
            {
                'id_sede': self.sede.id_sede,
                'fecha_entrega': '2026-11-11',
                'items': [{'id_ingrediente': self.leche.id_ingrediente, 'cantidad': 70, 'unidad': 'L'}],
            },
            format='json',
        )
        self.assertEqual(resp_bloqueado.status_code, 400)
        self.assertTrue(resp_bloqueado.data.get('requiere_autorizacion_exceso'))
        self.inv_central_leche.refresh_from_db()
        self.assertEqual(self.inv_central_leche.cantidad_disponible, Decimal('100.000'))

        # 2. Despachar 70 L CON autorización y justificación -> permitido (201) + descuenta + congela snapshot
        resp_ok = self.client.post(
            '/api/entregas/despacho-lote/',
            {
                'id_sede': self.sede.id_sede,
                'fecha_entrega': '2026-11-11',
                'autorizacion_exceso': True,
                'autorizado_por': 'Coordinación Regional PAE',
                'justificacion_exceso': 'Evento nutricional extraordinario de cobertura ampliada.',
                'items': [{'id_ingrediente': self.leche.id_ingrediente, 'cantidad': 70, 'unidad': 'L'}],
            },
            format='json',
        )
        self.assertEqual(resp_ok.status_code, 201)
        self.assertTrue(resp_ok.data['codigo_documento'].startswith('ENT-'))
        id_entrega = resp_ok.data['despachos'][0]['id_entrega']

        self.inv_central_leche.refresh_from_db()
        self.assertEqual(self.inv_central_leche.cantidad_disponible, Decimal('30.000'))

        # Modificar el gramaje DESPUÉS del despacho: el soporte auditable conserva el cálculo original
        self.g_leche_pre.cantidad_gramaje = '999.000'
        self.g_leche_pre.save()

        resp_soporte = self.client.get(f'/api/entregas/{id_entrega}/soporte-calculo/')
        self.assertEqual(resp_soporte.status_code, 200)
        soporte = resp_soporte.data
        self.assertEqual(soporte['id_contrato'], self.contrato.id_contrato)
        self.assertEqual(soporte['id_sede'], self.sede.id_sede)
        self.assertTrue(soporte['autorizacion_exceso'])
        self.assertEqual(soporte['autorizado_por'], 'Coordinación Regional PAE')
        self.assertEqual(soporte['consolidado_snapshot'][0]['cantidad_total_requerida'], 57.5)
        self.assertEqual(soporte['consolidado_snapshot'][0]['cantidad_despachada'], 70.0)
        self.assertEqual(CalculoEntrega.objects.count(), 1)