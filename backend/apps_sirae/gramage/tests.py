from decimal import Decimal
from datetime import date
from django.test import TestCase
from rest_framework.test import APIClient

from apps_sirae.asistencia_diaria.models import AsistenciaDiaria
from apps_sirae.categorias_inventario.models import CategoriaInventario
from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.detalle_plato.models import DetallePlato
from apps_sirae.grados.models import Grados, GrupoGramaje
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.instituciones.models import Institucion, SupervisorInstitucion
from apps_sirae.jornadas.models import Jornada
from apps_sirae.menus.models import Menu
from apps_sirae.platos.models import Plato
from apps_sirae.receta_componente.models import RecetaComponente
from apps_sirae.roles.models import Rol
from apps_sirae.secciones_menu.models import SeccionMenu
from apps_sirae.sede_jornada.models import SedeJornada, SedeJornadaGrado
from apps_sirae.sedes.models import Sede
from apps_sirae.unidades_medida.models import EquivalenciaUnidad, UnidadMedida
from apps_sirae.usuarios.models import Usuario
from .models import Gramage


def _fake_user(*, superadmin=False, supervisor=False):
    return type(
        'UsuarioPrueba',
        (),
        {
            'is_authenticated': True,
            'pk': 1 if superadmin else 2,
            'id_usuario': 1 if superadmin else 2,
            'es_super_administrador': lambda self: superadmin,
            'es_supervisor': lambda self: supervisor,
            'es_administrador': lambda self: False,
            'es_jefa_manipuladoras': lambda self: False,
        },
    )()


class GramajeCatalogoTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=_fake_user(superadmin=True))

        self.cat_carnes = CategoriaInventario.objects.create(nombre_categoria='Cárnicos')
        self.cat_granos = CategoriaInventario.objects.create(nombre_categoria='Granos')

        self.gramo = UnidadMedida.objects.create(
            nombre='Gramo', abreviatura='g', tipo_magnitud='MASA', factor_conversion_base=Decimal('1')
        )
        self.kg = UnidadMedida.objects.create(
            nombre='Kilogramo', abreviatura='kg', tipo_magnitud='MASA', factor_conversion_base=Decimal('1000')
        )
        self.litro = UnidadMedida.objects.create(
            nombre='Litro', abreviatura='L', tipo_magnitud='VOLUMEN', factor_conversion_base=Decimal('1000')
        )

        self.pollo = Ingrediente.objects.create(
            nombre_ingrediente='Pechuga de Pollo',
            id_categoria_inventario=self.cat_carnes,
            id_unidad_medida=self.kg,
            tipo_conservacion='perecedero',
        )
        self.frijol = Ingrediente.objects.create(
            nombre_ingrediente='Fríjol Cargamanto',
            id_categoria_inventario=self.cat_granos,
            id_unidad_medida=self.kg,
            tipo_conservacion='no_perecedero',
        )

        self.grupo_primaria = GrupoGramaje.objects.create(nombre='Primaria', nivel_educativo='PRIMARIA')
        self.grado_primero = Grados.objects.create(
            nombre_grado='Primero',
            id_grupo_gramaje=self.grupo_primaria,
            nivel_educativo='PRIMARIA',
        )

    def test_validaciones_obligatorias_y_cantidades_invalidas(self):
        resp_vacio = self.client.post('/api/gramage/', {}, format='json')
        self.assertEqual(resp_vacio.status_code, 400)
        for campo in ('id_ingrediente', 'id_grado', 'id_unidad_medida', 'cantidad_gramaje'):
            self.assertIn(campo, resp_vacio.data)

        resp_cero = self.client.post(
            '/api/gramage/',
            {
                'id_ingrediente': self.pollo.id_ingrediente,
                'id_grado': self.grado_primero.id_grado,
                'id_unidad_medida': self.gramo.id_unidad_medida,
                'cantidad_gramaje': '0',
            },
            format='json',
        )
        self.assertEqual(resp_cero.status_code, 400)

        resp_neg = self.client.post(
            '/api/gramage/',
            {
                'id_ingrediente': self.pollo.id_ingrediente,
                'id_grado': self.grado_primero.id_grado,
                'id_unidad_medida': self.gramo.id_unidad_medida,
                'cantidad_gramaje': '-25.5',
            },
            format='json',
        )
        self.assertEqual(resp_neg.status_code, 400)

    def test_crear_editar_conserva_valor_anterior_e_historial_y_no_duplica_activos(self):
        resp_crea = self.client.post(
            '/api/gramage/',
            {
                'id_ingrediente': self.pollo.id_ingrediente,
                'id_grado': self.grado_primero.id_grado,
                'id_unidad_medida': self.gramo.id_unidad_medida,
                'cantidad_gramage': '90.000',
                'contexto_aplicacion': 'ALMUERZO',
                'descripcion': 'Porción neta cocida según minuta PAE',
            },
            format='json',
        )
        self.assertEqual(resp_crea.status_code, 201)
        self.assertEqual(resp_crea.data['tipo_alimento_display'], 'Perecedero')
        self.assertEqual(resp_crea.data['estado'], 'ACTIVO')
        id_g = resp_crea.data['id_gramaje']

        # No duplicar activa para mismo producto + grado + contexto
        resp_dup = self.client.post(
            '/api/gramage/',
            {
                'id_ingrediente': self.pollo.id_ingrediente,
                'id_grado': self.grado_primero.id_grado,
                'id_unidad_medida': self.gramo.id_unidad_medida,
                'cantidad_gramaje': '95.000',
                'contexto_aplicacion': 'ALMUERZO',
            },
            format='json',
        )
        self.assertEqual(resp_dup.status_code, 400)

        # Sí permite mismo producto y grado en contexto distinto
        resp_otro_ctx = self.client.post(
            '/api/gramage/',
            {
                'id_ingrediente': self.pollo.id_ingrediente,
                'id_grado': self.grado_primero.id_grado,
                'id_unidad_medida': self.gramo.id_unidad_medida,
                'cantidad_gramaje': '60.000',
                'contexto_aplicacion': 'REFRIGERIO',
            },
            format='json',
        )
        self.assertEqual(resp_otro_ctx.status_code, 201)

        # Editar valor conserva valor_anterior y registra historial
        resp_edit = self.client.patch(
            f'/api/gramage/{id_g}/',
            {'cantidad_gramaje': '105.000', 'descripcion': 'Ajuste nutricional trimestral'},
            format='json',
        )
        self.assertEqual(resp_edit.status_code, 200)
        self.assertEqual(Decimal(str(resp_edit.data['valor_anterior'])), Decimal('90.000'))
        self.assertEqual(Decimal(str(resp_edit.data['cantidad_gramaje'])), Decimal('105.000'))

        # Inactivar sin perder historial, ni permitir delete destructivo
        resp_inact = self.client.post(f'/api/gramage/{id_g}/cambiar-estado/', format='json')
        self.assertEqual(resp_inact.status_code, 200)
        self.assertEqual(resp_inact.data['estado'], 'INACTIVO')

        resp_del = self.client.delete(f'/api/gramage/{id_g}/')
        self.assertEqual(resp_del.status_code, 400)

        resp_hist = self.client.get(f'/api/gramage/{id_g}/historial/')
        self.assertEqual(resp_hist.status_code, 200)
        self.assertEqual(len(resp_hist.data), 3)
        self.assertEqual(resp_hist.data[0]['tipo_evento'], 'INACTIVACION')
        self.assertEqual(resp_hist.data[1]['tipo_evento'], 'EDICION')
        self.assertEqual(Decimal(str(resp_hist.data[1]['cantidad_anterior'])), Decimal('90.000'))
        self.assertEqual(Decimal(str(resp_hist.data[1]['cantidad_nueva'])), Decimal('105.000'))

    def test_rechaza_unidad_incompatible_y_acepta_con_equivalencia(self):
        # Pollo base=kg (MASA), intentar asignar gramaje en Litro (VOLUMEN) sin equivalencia
        resp_incomp = self.client.post(
            '/api/gramage/',
            {
                'id_ingrediente': self.pollo.id_ingrediente,
                'id_grado': self.grado_primero.id_grado,
                'id_unidad_medida': self.litro.id_unidad_medida,
                'cantidad_gramaje': '0.150',
            },
            format='json',
        )
        self.assertEqual(resp_incomp.status_code, 400)
        self.assertIn('id_unidad_medida', resp_incomp.data)

        # Con equivalencia configurada para ese ingrediente ahora sí debe aceptarlo
        EquivalenciaUnidad.objects.create(
            id_ingrediente=self.pollo,
            id_unidad_origen=self.litro,
            id_unidad_destino=self.kg,
            factor_conversion=Decimal('1.000000'),
        )
        resp_ok = self.client.post(
            '/api/gramage/',
            {
                'id_ingrediente': self.pollo.id_ingrediente,
                'id_grado': self.grado_primero.id_grado,
                'id_unidad_medida': self.litro.id_unidad_medida,
                'cantidad_gramaje': '0.150',
            },
            format='json',
        )
        self.assertEqual(resp_ok.status_code, 201)

    def test_busqueda_y_filtros_por_grado_categoria_y_estado(self):
        g1 = Gramage.objects.create(
            id_ingrediente=self.pollo,
            id_grado=self.grado_primero,
            id_unidad_medida=self.gramo,
            cantidad_gramaje=Decimal('100'),
            estado='ACTIVO',
        )
        Gramage.objects.create(
            id_ingrediente=self.frijol,
            id_grado=self.grado_primero,
            id_unidad_medida=self.gramo,
            cantidad_gramaje=Decimal('45'),
            estado='INACTIVO',
        )

        r_search = self.client.get('/api/gramage/?search=Pechuga')
        res_search = r_search.data.get('results', r_search.data)
        self.assertEqual(len(res_search), 1)
        self.assertEqual(res_search[0]['id_gramaje'], g1.id_gramaje)

        r_cat = self.client.get(f'/api/gramage/?id_categoria={self.cat_granos.id_categoria_inventario}')
        res_cat = r_cat.data.get('results', r_cat.data)
        self.assertEqual(len(res_cat), 1)
        self.assertEqual(res_cat[0]['nombre_ingrediente'], 'Fríjol Cargamanto')

        r_est = self.client.get(f'/api/gramage/?id_grado={self.grado_primero.id_grado}&estado=ACTIVO')
        res_est = r_est.data.get('results', r_est.data)
        self.assertEqual(len(res_est), 1)

    def test_calculo_porciones_por_grupo_y_permisos_escritura(self):
        Gramage.objects.create(
            id_ingrediente=self.pollo,
            id_grado=self.grado_primero,
            id_unidad_medida=self.gramo,
            cantidad_gramaje=Decimal('100.000'),
            estado='ACTIVO',
        )
        self.client.force_authenticate(user=_fake_user(supervisor=True))

        # Lectura y cálculo permitidos para Supervisor
        r_calc = self.client.get(
            f'/api/gramage/calcular-porciones/?id_grupo_gramaje={self.grupo_primaria.id_grupo_gramaje}&estudiantes=50&dias=5'
        )
        self.assertEqual(r_calc.status_code, 200)
        # 100 g * 50 * 5 = 25000 g -> convertido a unidad base del pollo (kg) = 25.0 kg
        self.assertEqual(r_calc.data['resultados'][0]['cantidad_total_calculada'], 25.0)
        self.assertEqual(r_calc.data['resultados'][0]['unidad_resultado'], 'kg')

        # Escritura bloqueada para Supervisor
        r_post = self.client.post(
            '/api/gramage/',
            {
                'id_ingrediente': self.frijol.id_ingrediente,
                'id_grado': self.grado_primero.id_grado,
                'id_unidad_medida': self.gramo.id_unidad_medida,
                'cantidad_gramaje': '50',
            },
            format='json',
        )
        self.assertEqual(r_post.status_code, 403)


class ConsultaGramajesPorAlcanceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.gramo = UnidadMedida.objects.create(
            nombre='Gramo', abreviatura='g', tipo_magnitud='MASA', factor_conversion_base=Decimal('1')
        )
        self.kg = UnidadMedida.objects.create(
            nombre='Kilogramo', abreviatura='kg', tipo_magnitud='MASA', factor_conversion_base=Decimal('1000')
        )
        self.cat = CategoriaInventario.objects.create(nombre_categoria='Cárnicos y Granos')
        self.pollo = Ingrediente.objects.create(
            nombre_ingrediente='Pollo',
            id_categoria_inventario=self.cat,
            id_unidad_medida=self.kg,
            tipo_conservacion='perecedero',
        )
        self.arroz = Ingrediente.objects.create(
            nombre_ingrediente='Arroz',
            id_categoria_inventario=self.cat,
            id_unidad_medida=self.kg,
            tipo_conservacion='no_perecedero',
        )

        self.grupo_primaria = GrupoGramaje.objects.create(
            nombre='Primaria Test',
            nivel_educativo='PRIMARIA',
            estado='ACTIVO',
        )
        self.grado_primero = Grados.objects.create(
            nombre_grado='Primero',
            id_grupo_gramaje=self.grupo_primaria,
            nivel_educativo='PRIMARIA',
            estado='ACTIVO',
        )
        self.grado_segundo = Grados.objects.create(
            nombre_grado='Segundo',
            id_grupo_gramaje=self.grupo_primaria,
            nivel_educativo='PRIMARIA',
            estado='ACTIVO',
        )

        # Roles y usuarios reales
        self.rol_super, _ = Rol.objects.get_or_create(nombre=Rol.NombreRol.SUPER_ADMINISTRADOR)
        self.rol_sup, _ = Rol.objects.get_or_create(nombre=Rol.NombreRol.SUPERVISOR)
        self.rol_admin, _ = Rol.objects.get_or_create(nombre=Rol.NombreRol.ADMINISTRADOR)
        self.rol_jefa, _ = Rol.objects.get_or_create(nombre=Rol.NombreRol.JEFA_MANIPULADORAS)

        self.inst_a = Institucion.objects.create(nombre_institucion='IE Norte', nit='900111')
        self.inst_b = Institucion.objects.create(nombre_institucion='IE Sur', nit='900222')

        self.sede_a1 = Sede.objects.create(id_institucion=self.inst_a, nombre_sede='Sede Norte Principal')
        self.sede_a2 = Sede.objects.create(id_institucion=self.inst_a, nombre_sede='Sede Norte Anexa')
        self.sede_b1 = Sede.objects.create(id_institucion=self.inst_b, nombre_sede='Sede Sur Única')

        self.jornada_am = Jornada.objects.create(nombre_jornada='Mañana')
        self.jornada_pm = Jornada.objects.create(nombre_jornada='Tarde')

        self.sj_a1_am = SedeJornada.objects.create(id_sede=self.sede_a1, id_jornada=self.jornada_am, cupos=120)
        self.sj_a1_pm = SedeJornada.objects.create(id_sede=self.sede_a1, id_jornada=self.jornada_pm, cupos=90)
        self.sj_b1_am = SedeJornada.objects.create(id_sede=self.sede_b1, id_jornada=self.jornada_am, cupos=80)

        self.superadmin = Usuario.objects.create_user(
            correo='superadmin-hu4@test.com',
            nombre='Super',
            apellido='Admin',
            password='Password123!',
            numero_documento='SA100',
            rol=self.rol_super,
        )
        self.supervisor = Usuario.objects.create_user(
            correo='sup-hu4@test.com',
            nombre='Luis',
            apellido='Supervisor',
            password='Password123!',
            numero_documento='SUP100',
            rol=self.rol_sup,
        )
        SupervisorInstitucion.objects.create(id_supervisor=self.supervisor, id_institucion=self.inst_a)

        self.admin_b = Usuario.objects.create_user(
            correo='adminb-hu4@test.com',
            nombre='Ana',
            apellido='AdminB',
            password='Password123!',
            numero_documento='ADM100',
            rol=self.rol_admin,
            id_institucion=self.inst_b,
        )
        self.jefa_a1_am = Usuario.objects.create_user(
            correo='jefa-hu4@test.com',
            nombre='Marta',
            apellido='Jefa',
            password='Password123!',
            numero_documento='JEF100',
            rol=self.rol_jefa,
            id_institucion=self.inst_a,
            id_sede=self.sede_a1,
            id_jornada=self.jornada_am,
        )

        # Grados atendidos por sede y jornada
        SedeJornadaGrado.objects.create(id_sede_jornada=self.sj_a1_am, id_grado=self.grado_primero, cupos=60)
        SedeJornadaGrado.objects.create(id_sede_jornada=self.sj_a1_am, id_grado=self.grado_segundo, cupos=60)
        SedeJornadaGrado.objects.create(id_sede_jornada=self.sj_a1_pm, id_grado=self.grado_segundo, cupos=90)
        SedeJornadaGrado.objects.create(id_sede_jornada=self.sj_b1_am, id_grado=self.grado_primero, cupos=80)

        # Gramajes activos: Pollo para 1° y 2°; Arroz solo para 1° (falta Arroz en 2°)
        Gramage.objects.create(
            id_ingrediente=self.pollo,
            id_grado=self.grado_primero,
            id_unidad_medida=self.gramo,
            cantidad_gramaje=Decimal('90.000'),
            estado='ACTIVO',
        )
        Gramage.objects.create(
            id_ingrediente=self.pollo,
            id_grado=self.grado_segundo,
            id_unidad_medida=self.gramo,
            cantidad_gramaje=Decimal('100.000'),
            estado='ACTIVO',
        )
        Gramage.objects.create(
            id_ingrediente=self.arroz,
            id_grado=self.grado_primero,
            id_unidad_medida=self.gramo,
            cantidad_gramaje=Decimal('80.000'),
            estado='ACTIVO',
        )
        # Gramaje INACTIVO para Arroz en Segundo NO debe cubrir ni asumirse
        Gramage.objects.create(
            id_ingrediente=self.arroz,
            id_grado=self.grado_segundo,
            id_unidad_medida=self.gramo,
            cantidad_gramaje=Decimal('75.000'),
            contexto_aplicacion='ALMUERZO',
            estado='INACTIVO',
        )

        # Menú + Receta en Sede A1 / Jornada Mañana requiere Pollo y Arroz
        contrato_a1 = Contrato.objects.create(
            numero_cor='CONT-A1',
            id_institucion=self.inst_a,
            id_sede=self.sede_a1,
            id_jornada=self.jornada_am,
            cupos=120,
        )
        seccion_am = SeccionMenu.objects.create(id_jornada=self.jornada_am, nombre_seccion='Almuerzo')
        plato = Plato.objects.create(id_seccion=seccion_am, nombre_plato='Arroz con Pollo')
        menu = Menu.objects.create(
            id_contrato=contrato_a1.id_contrato,
            id_jornada=self.jornada_am,
            fecha=date(2026, 11, 11),
            ninos_presentes=120,
            estado='ACTIVO',
            informacion_nutricional='Menú de prueba',
        )
        DetallePlato.objects.create(id_menu=menu.id_menu, id_plato=plato, porcion_por_nino=Decimal('1'))
        RecetaComponente.objects.create(id_plato=plato, id_ingrediente=self.pollo, cantidad=Decimal('100'))
        RecetaComponente.objects.create(id_plato=plato, id_ingrediente=self.arroz, cantidad=Decimal('80'))

    def test_superadmin_asigna_grados_a_sede_jornada(self):
        self.client.force_authenticate(user=self.superadmin)
        resp = self.client.patch(
            f'/api/sede-jornadas/{self.sj_a1_pm.id_sede_jornada}/',
            {'grados_ids': [self.grado_primero.id_grado, self.grado_segundo.id_grado]},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.data['grados_ids']), {self.grado_primero.id_grado, self.grado_segundo.id_grado})

    def test_supervisor_solo_consulta_instituciones_y_sedes_asignadas(self):
        self.client.force_authenticate(user=self.supervisor)
        resp = self.client.get('/api/gramage/consultar-por-alcance/')
        self.assertEqual(resp.status_code, 200)
        inst_ids = {sj['id_institucion'] for sj in resp.data['sede_jornadas']}
        self.assertEqual(inst_ids, {self.inst_a.id_institucion})
        self.assertFalse(resp.data['permisos']['puede_modificar_gramajes'])

        # Intento explícito de consultar otra institución fuera de su alcance -> 403
        resp_forbidden = self.client.get(
            f'/api/gramage/consultar-por-alcance/?id_institucion={self.inst_b.id_institucion}'
        )
        self.assertEqual(resp_forbidden.status_code, 403)

    def test_admin_institucional_solo_consulta_su_institucion_y_sedes(self):
        self.client.force_authenticate(user=self.admin_b)
        resp = self.client.get('/api/gramage/consultar-por-alcance/')
        self.assertEqual(resp.status_code, 200)
        inst_ids = {sj['id_institucion'] for sj in resp.data['sede_jornadas']}
        sede_ids = {sj['id_sede'] for sj in resp.data['sede_jornadas']}
        self.assertEqual(inst_ids, {self.inst_b.id_institucion})
        self.assertEqual(sede_ids, {self.sede_b1.id_sede})

        # No puede consultar sede de otra institución -> 403
        resp_forbidden = self.client.get(
            f'/api/gramage/consultar-por-alcance/?id_sede={self.sede_a1.id_sede}'
        )
        self.assertEqual(resp_forbidden.status_code, 403)

        # No puede modificar gramajes generales -> 403
        r_patch = self.client.patch(
            f'/api/sede-jornadas/{self.sj_b1_am.id_sede_jornada}/',
            {'cupos': 999},
            format='json',
        )
        self.assertEqual(r_patch.status_code, 403)

    def test_jefa_solo_consulta_su_sede_y_jornada_y_alerta_si_falta_gramaje_requerido(self):
        self.client.force_authenticate(user=self.jefa_a1_am)
        resp = self.client.get('/api/gramage/consultar-por-alcance/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['sede_jornadas']), 1)

        sj_data = resp.data['sede_jornadas'][0]
        self.assertEqual(sj_data['id_sede'], self.sede_a1.id_sede)
        self.assertEqual(sj_data['id_jornada'], self.jornada_am.id_jornada)
        self.assertEqual(sj_data['total_grados'], 2)

        # Verificar alerta explícita para Segundo grado sin gramaje activo de Arroz
        alertas_segundo = [
            al for al in resp.data['alertas_faltantes']
            if al['id_grado'] == self.grado_segundo.id_grado
            and al['id_ingrediente'] == self.arroz.id_ingrediente
        ]
        self.assertEqual(len(alertas_segundo), 1)
        self.assertEqual(alertas_segundo[0]['tipo'], 'FALTA_GRAMAJE_REQUERIDO')
        self.assertIsNone(alertas_segundo[0]['cantidad_gramaje'])

        # No puede consultar otra jornada ni otra sede -> 403
        r_otra_jornada = self.client.get(
            f'/api/gramage/consultar-por-alcance/?id_jornada={self.jornada_pm.id_jornada}'
        )
        self.assertEqual(r_otra_jornada.status_code, 403)
        r_otra_sede = self.client.get(
            f'/api/gramage/consultar-por-alcance/?id_sede={self.sede_a2.id_sede}'
        )
        self.assertEqual(r_otra_sede.status_code, 403)

        # Tampoco puede modificar gramajes generales
        r_post = self.client.post('/api/gramage/', {}, format='json')
        self.assertEqual(r_post.status_code, 403)

    def test_jefa_sin_jornada_asignada_emite_alerta_y_no_filtra_otras_jornadas(self):
        self.jefa_a1_am.id_jornada = None
        self.jefa_a1_am.save(update_fields=['id_jornada'])
        self.client.force_authenticate(user=self.jefa_a1_am)

        resp = self.client.get('/api/gramage/consultar-por-alcance/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['sede_jornadas'], [])
        self.assertTrue(len(resp.data['alertas_alcance']) >= 1)

    def test_calculo_asistencia_ignora_inactivos_y_alerta_faltante(self):
        AsistenciaDiaria.objects.create(
            id_grado=self.grado_segundo,
            fecha=date(2026, 11, 11),
            ninos_presentes=30,
        )
        self.client.force_authenticate(user=self.jefa_a1_am)
        resp = self.client.get(
            f'/api/asistencia_diaria/calculo/?grado={self.grado_segundo.id_grado}'
            f'&fecha=2026-11-11&id_sede={self.sede_a1.id_sede}&id_jornada={self.jornada_am.id_jornada}'
        )
        self.assertEqual(resp.status_code, 200)
        # Solo Pollo (activo); el Arroz INACTIVO NO debe usarse
        self.assertEqual(len(resp.data['calculo_ingredientes']), 1)
        self.assertEqual(resp.data['calculo_ingredientes'][0]['id_ingrediente'], self.pollo.id_ingrediente)
        self.assertEqual(len(resp.data['alertas_faltantes']), 1)
        self.assertEqual(resp.data['alertas_faltantes'][0]['id_ingrediente'], self.arroz.id_ingrediente)
        self.assertIsNone(resp.data['alertas_faltantes'][0]['cantidad_por_nino'])
