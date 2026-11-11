from datetime import date, time
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps_sirae.asistencia_diaria.models import AsistenciaDiaria
from apps_sirae.categorias_inventario.models import CategoriaInventario
from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.detalle_plato.models import DetallePlato
from apps_sirae.entregas.models import Entrega
from apps_sirae.grados.models import Grados, GrupoGramaje
from apps_sirae.gramage.models import Gramage
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.instituciones.models import Institucion, SupervisorInstitucion
from apps_sirae.inventario.models import Inventario
from apps_sirae.jornadas.models import Jornada
from apps_sirae.menus.models import Menu
from apps_sirae.platos.models import Plato
from apps_sirae.preparacion_asignada.models import PreparacionAsignada
from apps_sirae.receta_componente.models import RecetaComponente
from apps_sirae.reportes.models import PlanillaGenerada, PlantillaOficial
from apps_sirae.roles.models import Rol
from apps_sirae.salidas_inventario.models import SalidaInventario
from apps_sirae.sede_jornada.models import SedeJornada, SedeJornadaGrado
from apps_sirae.sedes.models import Sede
from apps_sirae.tipos_mercado.models import TipoMercado
from apps_sirae.turnos.models import Turno
from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.usuarios.models import Usuario


class ReportesSIR170a173Tests(TestCase):
    """
    Pruebas integrales para SIR-170 (plantillas), SIR-171 (planillas auto-diligenciadas),
    SIR-172 (consulta y filtros por alcance/rol) y SIR-173 (reportes consolidados reales).
    """

    def setUp(self):
        self.client = APIClient()
        self.rol_superadmin, _ = Rol.objects.get_or_create(nombre=Rol.NombreRol.SUPER_ADMINISTRADOR)
        self.rol_supervisor, _ = Rol.objects.get_or_create(nombre=Rol.NombreRol.SUPERVISOR)
        self.rol_admin, _ = Rol.objects.get_or_create(nombre=Rol.NombreRol.ADMINISTRADOR)
        self.rol_jefa, _ = Rol.objects.get_or_create(nombre=Rol.NombreRol.JEFA_MANIPULADORAS)

        self.inst_a = Institucion.objects.create(nombre_institucion='IE Real Norte', nit='900111222')
        self.inst_b = Institucion.objects.create(nombre_institucion='IE Real Sur', nit='900333444')

        self.sede_a1 = Sede.objects.create(
            id_institucion=self.inst_a,
            nombre_sede='Sede Principal Norte',
            codigo_dane='119001000111',
            estado='ACTIVO',
        )
        self.sede_a2 = Sede.objects.create(
            id_institucion=self.inst_a,
            nombre_sede='Sede Anexa Norte',
            codigo_dane='119001000222',
            estado='ACTIVO',
        )
        self.sede_b1 = Sede.objects.create(
            id_institucion=self.inst_b,
            nombre_sede='Sede Única Sur',
            codigo_dane='119001000333',
            estado='ACTIVO',
        )

        self.superadmin = Usuario.objects.create_user(
            correo='super-rep@test.com', nombre='Carlos', apellido='Super',
            password='Password123!', numero_documento='SA9001', rol=self.rol_superadmin,
        )
        self.supervisor_a = Usuario.objects.create_user(
            correo='sup-a@test.com', nombre='Lucía', apellido='Supervisora',
            password='Password123!', numero_documento='SUP9001', rol=self.rol_supervisor,
        )
        SupervisorInstitucion.objects.create(id_supervisor=self.supervisor_a, id_institucion=self.inst_a)

        self.admin_a = Usuario.objects.create_user(
            correo='adm-a@test.com', nombre='Mario', apellido='AdminA',
            password='Password123!', numero_documento='ADM9001', rol=self.rol_admin,
            id_institucion=self.inst_a,
        )
        self.jornada_am = Jornada.objects.create(nombre_jornada='Mañana')
        self.jornada_pm = Jornada.objects.create(nombre_jornada='Tarde')

        self.jefa_a1_am = Usuario.objects.create_user(
            correo='jefa-a1@test.com', nombre='Rosa', apellido='CocinaA1',
            password='Password123!', numero_documento='JEF9001', rol=self.rol_jefa,
            id_institucion=self.inst_a, id_sede=self.sede_a1, id_jornada=self.jornada_am,
        )

        self.sj_a1_am = SedeJornada.objects.create(id_sede=self.sede_a1, id_jornada=self.jornada_am, cupos=100)
        self.sj_a2_am = SedeJornada.objects.create(id_sede=self.sede_a2, id_jornada=self.jornada_am, cupos=50)
        self.sj_b1_am = SedeJornada.objects.create(id_sede=self.sede_b1, id_jornada=self.jornada_am, cupos=80)

        self.grupo = GrupoGramaje.objects.create(nombre='Primaria', nivel_educativo='PRIMARIA')
        self.grado_primero = Grados.objects.create(
            nombre_grado='Primero', id_grupo_gramaje=self.grupo, nivel_educativo='PRIMARIA', estado='ACTIVO'
        )
        SedeJornadaGrado.objects.create(
            id_sede_jornada=self.sj_a1_am, id_grado=self.grado_primero, cupos=100, estado='ACTIVO'
        )
        SedeJornadaGrado.objects.create(
            id_sede_jornada=self.sj_a2_am, id_grado=self.grado_primero, cupos=50, estado='ACTIVO'
        )
        SedeJornadaGrado.objects.create(
            id_sede_jornada=self.sj_b1_am, id_grado=self.grado_primero, cupos=80, estado='ACTIVO'
        )

        self.contrato_a = Contrato.objects.create(
            numero_cor='CTR-NORTE-2026',
            institucion='Operador Nutricional Real S.A.',
            zona='Urbana Real',
            fecha_inicio=date(2026, 1, 15),
            fecha_fin=date(2026, 11, 30),
            estado='ACTIVO',
            id_institucion=self.inst_a,
            id_sede=self.sede_a1,
            id_usuario_supervisor=self.supervisor_a,
            id_jornada=self.jornada_am,
            cupos=100,
            periodicidad_perecederos='SEMANAL',
            dias_cobertura_perecederos=5,
            periodicidad_no_perecederos='MENSUAL',
            dias_cobertura_no_perecederos=10,
        )
        self.contrato_b = Contrato.objects.create(
            numero_cor='CTR-SUR-2026',
            institucion='Operador Sur Ltda',
            fecha_inicio=date(2026, 1, 15),
            fecha_fin=date(2026, 11, 30),
            estado='ACTIVO',
            id_institucion=self.inst_b,
            id_sede=self.sede_b1,
            id_jornada=self.jornada_am,
            cupos=80,
        )

        self.u_g = UnidadMedida.objects.create(
            nombre='Gramo', abreviatura='g', tipo_magnitud='MASA', factor_conversion_base=Decimal('1.000000')
        )
        self.u_kg = UnidadMedida.objects.create(
            nombre='Kilogramo', abreviatura='kg', tipo_magnitud='MASA', factor_conversion_base=Decimal('1000.000000')
        )
        self.cat = CategoriaInventario.objects.create(nombre_categoria='Granos y Cereales')
        self.tm_noper = TipoMercado.objects.create(nombre_tipo='No perecedero')

        self.arroz = Ingrediente.objects.create(
            nombre_ingrediente='Arroz Integral Real',
            id_categoria_inventario=self.cat,
            id_unidad_medida=self.u_kg,
            tipo_conservacion='no_perecedero',
            id_tipo_mercado=self.tm_noper,
        )
        # 50 g por ración * 100 cupos * 10 días = 50,000 g = 50 kg programados
        Gramage.objects.create(
            id_ingrediente=self.arroz,
            id_grado=self.grado_primero,
            id_unidad_medida=self.u_g,
            cantidad_gramaje=Decimal('50.000'),
            estado='ACTIVO',
        )

        self.menu_a = Menu.objects.create(
            id_jornada=self.jornada_am,
            fecha=date(2026, 5, 10),
            ninos_presentes=95,
            estado='ACTIVO',
            id_contrato=self.contrato_a.id_contrato,
        )
        self.plato = Plato.objects.create(nombre_plato='Arroz con Verduras', componente='Cereal')
        DetallePlato.objects.create(id_menu=self.menu_a.id_menu, id_plato=self.plato, porcion_por_nino=Decimal('50.00'))
        RecetaComponente.objects.create(
            id_plato=self.plato, id_ingrediente=self.arroz, cantidad=Decimal('50.00'), base_cantidad='POR_NINO'
        )
        turno = Turno.objects.create(nombre_turno='Mañana')
        PreparacionAsignada.objects.create(
            id_menu=self.menu_a,
            id_plato=self.plato,
            id_usuario_manipuladora=self.jefa_a1_am,
            id_turno=turno,
            fecha=date(2026, 5, 10),
            hora_programada=time(7, 30),
            estado_preparacion='COMPLETADA',
        )

        Entrega.objects.create(
            id_ingrediente=self.arroz.id_ingrediente,
            id_usuario_supervisor=self.supervisor_a.id_usuario,
            id_tipo_mercado=self.tm_noper.id_tipo_mercado,
            fecha_entrega=date(2026, 5, 8),
            fecha_vencimiento=date(2026, 8, 30),
            cantidad=Decimal('45.00'),
            unidad='kg',
            id_institucion=self.inst_a,
            id_sede=self.sede_a1,
            id_contrato=self.contrato_a,
            documento_entrega='REM-REAL-001',
            cantidad_requerida_calculo=Decimal('50.000'),
            estado='CON_NOVEDAD',
            cantidad_recibida=Decimal('42.00'),
            cantidad_rechazada=Decimal('3.00'),
            motivo_rechazo='Bolsa averiada',
        )
        Entrega.objects.create(
            id_ingrediente=self.arroz.id_ingrediente,
            id_usuario_supervisor=self.superadmin.id_usuario,
            id_tipo_mercado=self.tm_noper.id_tipo_mercado,
            fecha_entrega=date(2026, 5, 8),
            fecha_vencimiento=date(2026, 8, 30),
            cantidad=Decimal('80.00'),
            unidad='kg',
            id_institucion=self.inst_b,
            id_sede=self.sede_b1,
            id_contrato=self.contrato_b,
            documento_entrega='REM-SUR-001',
            estado='RECIBIDA',
            cantidad_recibida=Decimal('80.00'),
        )

        Inventario.objects.create(
            id_ingrediente=self.arroz.id_ingrediente,
            cantidad_actual=Decimal('12.00'),
            stock_minimo=Decimal('15.00'),
            id_unidad_medida=self.u_kg.id_unidad_medida,
            id_institucion=self.inst_a,
            id_sede=self.sede_a1,
        )
        SalidaInventario.objects.create(
            id_ingrediente=self.arroz,
            id_usuario=self.jefa_a1_am,
            cantidad=Decimal('30.00'),
            id_unidad_medida=self.u_kg,
            observaciones='Preparación ciclo 1',
        )
        AsistenciaDiaria.objects.create(
            id_grado=self.grado_primero,
            fecha=date(2026, 5, 10),
            ninos_presentes=95,
            id_usuario_manipuladora=self.jefa_a1_am.id_usuario,
        )

    def test_sir170_ciclo_vida_plantilla_inmutabilidad_preview_y_versionado(self):
        # Roles no superadmin no pueden crear plantillas
        self.client.force_authenticate(user=self.supervisor_a)
        r_forb = self.client.post('/api/reportes/plantillas/', {
            'codigo': 'NO-AUTH',
            'nombre': 'No permitido',
            'categoria_proceso': 'REMISION',
        }, format='json')
        self.assertEqual(r_forb.status_code, 403)

        # Superadministrador crea plantilla con sección, campos automáticos/manuales, tabla, fórmula y conversión g->kg
        self.client.force_authenticate(user=self.superadmin)
        payload = {
            'codigo': 'PAE-CUSTOM-01',
            'nombre': 'Plantilla Verificación Remisión Personalizada',
            'descripcion': 'Control personalizado de remisiones con conversión y fórmula.',
            'categoria_proceso': 'REMISION',
            'finalidad': 'Validar despacho vs programación real',
            'roles_autorizados': ['SuperAdministrador', 'supervisor', 'Administrador'],
            'esquema': {
                'encabezado': {'titulo': 'VERIFICACIÓN CUSTOM', 'codigo_formato': 'PAE-CUSTOM-01'},
                'secciones': [
                    {'codigo': 'SEC_GEN', 'titulo': 'Datos Base', 'orden': 1, 'origen': 'AUTOMATICO', 'fuente_sirae': 'CONTRATO'},
                    {'codigo': 'SEC_DET', 'titulo': 'Productos', 'orden': 2, 'origen': 'AUTOMATICO', 'fuente_sirae': 'CONSUMO'},
                ],
                'campos': [
                    {'codigo': 'inst_nom', 'etiqueta': 'Institución', 'seccion': 'SEC_GEN', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'fuente_sirae': 'INSTITUCION', 'campo_fuente': 'nombre_institucion', 'requerido': True},
                    {'codigo': 'nota_sup', 'etiqueta': 'Nota de auditoría', 'seccion': 'SEC_GEN', 'tipo': 'TEXTO', 'origen': 'MANUAL', 'requerido': False},
                ],
                'tablas': [
                    {
                        'codigo': 'TBL_TEST',
                        'titulo': 'Comparativo',
                        'seccion': 'SEC_DET',
                        'fuente_sirae': 'CONSUMO',
                        'columnas': [
                            {'codigo': 'nombre_ingrediente', 'etiqueta': 'Producto', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO'},
                            {'codigo': 'cantidad_programada', 'etiqueta': 'Programado', 'tipo': 'NUMERO', 'origen': 'AUTOMATICO', 'calcular_total': True},
                            {'codigo': 'cantidad_programada_g', 'etiqueta': 'Programado (g)', 'tipo': 'NUMERO', 'origen': 'AUTOMATICO', 'calcular_total': True},
                            {'codigo': 'cantidad_despachada', 'etiqueta': 'Despachado', 'tipo': 'NUMERO', 'origen': 'AUTOMATICO', 'calcular_total': True},
                            {'codigo': 'dif', 'etiqueta': 'Diferencia', 'tipo': 'NUMERO', 'origen': 'AUTOMATICO', 'formula': 'cantidad_despachada - cantidad_programada', 'calcular_total': True},
                        ],
                        'conversiones_unidad': [
                            {
                                'codigo': 'CONV_KG_G',
                                'nombre': 'Kilogramos a Gramos',
                                'columna_origen': 'cantidad_programada',
                                'columna_destino': 'cantidad_programada_g',
                                'unidad_origen_abrev': 'kg',
                                'unidad_destino_abrev': 'g',
                                'aplicar_automaticamente': True,
                            }
                        ],
                    }
                ],
            },
        }
        r_create = self.client.post('/api/reportes/plantillas/', payload, format='json')
        self.assertEqual(r_create.status_code, 201, r_create.data)
        plantilla_id = r_create.data['id_plantilla']
        v1_id = r_create.data['version_borrador']['id_version']

        # Previsualización antes de publicar contra sede real A1
        r_prev = self.client.post(f'/api/reportes/plantillas/{plantilla_id}/previsualizar/', {
            'id_institucion': self.inst_a.id_institucion,
            'id_sede': self.sede_a1.id_sede,
        }, format='json')
        self.assertEqual(r_prev.status_code, 200, r_prev.data)
        self.assertEqual(r_prev.data['estado_version'], 'BORRADOR')
        tbl = r_prev.data['preview']['tablas'][0]
        self.assertEqual(tbl['filas'][0]['nombre_ingrediente'], 'Arroz Integral Real')
        self.assertEqual(tbl['filas'][0]['cantidad_programada'], 50.0)
        self.assertEqual(tbl['filas'][0]['cantidad_programada_g'], 50000.0)
        self.assertEqual(tbl['filas'][0]['cantidad_despachada'], 45.0)
        self.assertEqual(tbl['filas'][0]['dif'], -5.0)
        self.assertEqual(PlanillaGenerada.objects.count(), 0)

        # Publicación
        r_pub = self.client.post(f'/api/reportes/plantillas/{plantilla_id}/publicar/', {}, format='json')
        self.assertEqual(r_pub.status_code, 200)
        self.assertEqual(r_pub.data['version']['estado'], 'PUBLICADA')

        # Inmutabilidad: intentar editar versión publicada debe fallar
        r_edit_pub = self.client.patch(f'/api/reportes/plantillas/{plantilla_id}/', {
            'id_version': v1_id,
            'esquema': {'encabezado': {'titulo': 'ALTERADA'}, 'secciones': [], 'campos': [], 'tablas': []},
        }, format='json')
        self.assertEqual(r_edit_pub.status_code, 400)

        # Generar planilla sobre v1 y luego crear v2 sin afectar histórico
        r_gen = self.client.post('/api/reportes/planillas/generar/', {
            'id_plantilla': plantilla_id,
            'id_institucion': self.inst_a.id_institucion,
            'id_sede': self.sede_a1.id_sede,
            'periodo': '2026-05',
        }, format='json')
        self.assertEqual(r_gen.status_code, 201, r_gen.data)
        self.assertEqual(r_gen.data['planilla']['version_numero'], 1)

        r_nv = self.client.post(f'/api/reportes/plantillas/{plantilla_id}/nueva-version/', {
            'notas_version': 'Versión 2 con nuevo campo',
        }, format='json')
        self.assertEqual(r_nv.status_code, 201)
        self.assertEqual(r_nv.data['version']['numero_version'], 2)
        self.assertEqual(r_nv.data['version']['estado'], 'BORRADOR')

        # Versión histórica de la planilla sigue en v1 incluso tras publicar v2
        r_pub2 = self.client.post(f'/api/reportes/plantillas/{plantilla_id}/publicar/', {
            'id_version': r_nv.data['version']['id_version'],
        }, format='json')
        self.assertEqual(r_pub2.status_code, 200)
        planilla_db = PlanillaGenerada.objects.get(id_planilla=r_gen.data['planilla']['id_planilla'])
        self.assertEqual(planilla_db.id_plantilla_version.numero_version, 1)

    def test_sir171_generacion_real_pendientes_borrador_y_no_duplicados(self):
        self.client.force_authenticate(user=self.supervisor_a)

        # Generar planilla oficial de CONSUMO para Sede A1 -> trae datos reales de BD
        r_gen = self.client.post('/api/reportes/planillas/generar/', {
            'categoria_proceso': 'CONSUMO',
            'id_institucion': self.inst_a.id_institucion,
            'id_sede': self.sede_a1.id_sede,
            'periodo': '2026-05-C1',
        }, format='json')
        self.assertEqual(r_gen.status_code, 201, r_gen.data)
        pln = r_gen.data['planilla']
        snap = pln['contenido_snapshot']

        self.assertEqual(snap['encabezado']['institucion']['nombre'], 'IE Real Norte')
        self.assertEqual(snap['encabezado']['sede']['codigo_dane'], '119001000111')
        self.assertEqual(snap['encabezado']['contrato']['numero_cor'], 'CTR-NORTE-2026')
        self.assertEqual(snap['encabezado']['contrato']['operador'], 'Operador Nutricional Real S.A.')
        self.assertEqual(snap['responsables']['supervisor'], 'Lucía Supervisora')
        self.assertEqual(snap['responsables']['administrador_institucional'], 'Mario AdminA')
        self.assertEqual(snap['responsables']['jefa_manipuladoras'], 'Rosa CocinaA1')
        self.assertEqual(snap['totales_cadena']['total_programado'], 50.0)
        self.assertEqual(snap['totales_cadena']['total_despachado'], 45.0)
        self.assertEqual(snap['totales_cadena']['total_recibido'], 42.0)
        self.assertEqual(snap['totales_cadena']['total_consumido'], 30.0)
        self.assertIn(self.contrato_a.id_contrato, pln['registros_origen']['contrato_ids'])

        # Evitar duplicados para mismo proceso + sede + periodo
        r_dup = self.client.post('/api/reportes/planillas/generar/', {
            'categoria_proceso': 'CONSUMO',
            'id_institucion': self.inst_a.id_institucion,
            'id_sede': self.sede_a1.id_sede,
            'periodo': '2026-05-C1',
        }, format='json')
        self.assertEqual(r_dup.status_code, 400)

        # Generar planilla de ASISTENCIA en Sede B1 donde no hay asistencia ni contrato supervisor -> BORRADOR con PENDIENTE
        self.client.force_authenticate(user=self.superadmin)
        r_borr = self.client.post('/api/reportes/planillas/generar/', {
            'categoria_proceso': 'ASISTENCIA',
            'id_institucion': self.inst_b.id_institucion,
            'id_sede': self.sede_b1.id_sede,
            'periodo': '2026-05-C1',
        }, format='json')
        self.assertEqual(r_borr.status_code, 201)
        self.assertEqual(r_borr.data['planilla']['estado'], 'BORRADOR')
        self.assertTrue(len(r_borr.data['planilla']['campos_pendientes']) > 0)

    def test_sir172_consulta_aislamiento_por_rol_y_descarga(self):
        self.client.force_authenticate(user=self.superadmin)
        r_a1 = self.client.post('/api/reportes/planillas/generar/', {
            'categoria_proceso': 'REMISION',
            'id_institucion': self.inst_a.id_institucion,
            'id_sede': self.sede_a1.id_sede,
            'id_jornada': self.jornada_am.id_jornada,
            'periodo': '2026-05',
        }, format='json').data['planilla']['id_planilla']
        r_a2 = self.client.post('/api/reportes/planillas/generar/', {
            'categoria_proceso': 'REMISION',
            'id_institucion': self.inst_a.id_institucion,
            'id_sede': self.sede_a2.id_sede,
            'id_jornada': self.jornada_am.id_jornada,
            'periodo': '2026-05',
        }, format='json').data['planilla']['id_planilla']
        r_b1 = self.client.post('/api/reportes/planillas/generar/', {
            'categoria_proceso': 'REMISION',
            'id_institucion': self.inst_b.id_institucion,
            'id_sede': self.sede_b1.id_sede,
            'id_jornada': self.jornada_am.id_jornada,
            'periodo': '2026-05',
        }, format='json').data['planilla']['id_planilla']

        # Superadmin ve las 3
        resp_sa = self.client.get('/api/reportes/planillas/').data
        items_sa = resp_sa['results'] if isinstance(resp_sa, dict) and 'results' in resp_sa else resp_sa
        self.assertEqual(len(items_sa), 3)

        # Supervisor A solo ve inst A (r_a1 y r_a2), nunca r_b1
        self.client.force_authenticate(user=self.supervisor_a)
        resp_sup = self.client.get('/api/reportes/planillas/').data
        items_sup = resp_sup['results'] if isinstance(resp_sup, dict) and 'results' in resp_sup else resp_sup
        ids_sup = {p['id_planilla'] for p in items_sup}
        self.assertEqual(ids_sup, {r_a1, r_a2})
        self.assertEqual(self.client.get(f'/api/reportes/planillas/{r_b1}/').status_code, 404)

        # Administrador A solo ve inst A
        self.client.force_authenticate(user=self.admin_a)
        resp_adm = self.client.get('/api/reportes/planillas/').data
        items_adm = resp_adm['results'] if isinstance(resp_adm, dict) and 'results' in resp_adm else resp_adm
        ids_adm = {p['id_planilla'] for p in items_adm}
        self.assertEqual(ids_adm, {r_a1, r_a2})

        # Jefa A1 solo ve Sede A1 (r_a1)
        self.client.force_authenticate(user=self.jefa_a1_am)
        resp_jefa = self.client.get('/api/reportes/planillas/').data
        items_jefa = resp_jefa['results'] if isinstance(resp_jefa, dict) and 'results' in resp_jefa else resp_jefa
        ids_jefa = {p['id_planilla'] for p in items_jefa}
        self.assertEqual(ids_jefa, {r_a1})

        # Descarga CSV real
        r_csv = self.client.get(f'/api/reportes/planillas/{r_a1}/descargar/?formato=csv')
        self.assertEqual(r_csv.status_code, 200)
        self.assertIn('IE Real Norte', r_csv.content.decode('utf-8'))

        # Cierre operativo impide ediciones posteriores
        self.client.force_authenticate(user=self.supervisor_a)
        r_val = self.client.post(f'/api/reportes/planillas/{r_a1}/actualizar/', {
            'observaciones': 'Verificado conforme contra bodega',
            'estado': 'CERRADO',
        }, format='json')
        self.assertEqual(r_val.status_code, 200)
        self.assertEqual(r_val.data['estado'], 'CERRADO')
        r_lock = self.client.post(f'/api/reportes/planillas/{r_a1}/actualizar/', {'observaciones': 'Cambio tardío'}, format='json')
        self.assertEqual(r_lock.status_code, 400)

    def test_sir173_reportes_consolidados_reales_y_seguridad_alcance(self):
        # Supervisor A solo consulta su institución A (sin mezclar los 80kg de Institución B)
        self.client.force_authenticate(user=self.supervisor_a)
        r_rep = self.client.get('/api/reportes/consolidados/?tipo_reporte=CONSUMO_ALIMENTOS')
        self.assertEqual(r_rep.status_code, 200, r_rep.data)
        res = r_rep.data['resumen_ejecutivo']
        self.assertEqual(res['instituciones_autorizadas'], 1)
        self.assertEqual(res['sedes_autorizadas'], 2)
        self.assertEqual(res['total_cupos'], 150)
        # Consolidado multi-sede de Inst A: Sede A1 (50kg) + Sede A2 (50kg) = 100kg programados
        self.assertEqual(res['productos_programados'], 100.0)
        self.assertEqual(res['productos_despachados'], 45.0)
        self.assertEqual(res['productos_recibidos'], 42.0)
        self.assertEqual(res['productos_consumidos'], 30.0)
        self.assertEqual(res['productos_bajo_minimo'], 1)
        self.assertEqual(res['asistencia_acumulada'], 95)
        self.assertTrue(bool(r_rep.data['fecha_actualizacion']))

        # Al filtrar estrictamente a Sede A1 reporta exactamente 50kg
        r_sede = self.client.get(f'/api/reportes/consolidados/?tipo_reporte=CONSUMO_ALIMENTOS&id_sede={self.sede_a1.id_sede}')
        self.assertEqual(r_sede.status_code, 200)
        self.assertEqual(r_sede.data['resumen_ejecutivo']['productos_programados'], 50.0)

        # Supervisor A NO puede consultar institución B
        r_forb = self.client.get(f'/api/reportes/consolidados/?id_institucion={self.inst_b.id_institucion}')
        self.assertEqual(r_forb.status_code, 403)

        # Novedades reales incluyen entrega CON_NOVEDAD + inventario bajo mínimo
        r_nov = self.client.get('/api/reportes/consolidados/?tipo_reporte=NOVEDADES_INCONSISTENCIAS')
        self.assertEqual(r_nov.status_code, 200)
        origenes = {n['origen'] for n in r_nov.data['detalle']}
        self.assertIn('ENTREGA_RECEPCION', origenes)
        self.assertIn('INVENTARIO', origenes)

        # Exportación CSV real de consolidado
        r_csv = self.client.get('/api/reportes/consolidados/?tipo_reporte=RECEPCIONES_DIFERENCIAS&formato=csv')
        self.assertEqual(r_csv.status_code, 200)
        self.assertIn('Arroz Integral Real', r_csv.content.decode('utf-8'))
