from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient

from apps_sirae.categorias_inventario.models import CategoriaInventario
from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.detalle_plato.models import DetallePlato
from apps_sirae.grados.models import Grados, GrupoGramaje
from apps_sirae.gramage.models import Gramage
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.instituciones.models import Institucion, SupervisorInstitucion
from apps_sirae.jornadas.models import Jornada
from apps_sirae.menus.models import Menu
from apps_sirae.platos.models import Plato
from apps_sirae.receta_componente.models import RecetaComponente
from apps_sirae.roles.models import Rol
from apps_sirae.sede_jornada.models import SedeJornada, SedeJornadaGrado
from apps_sirae.sedes.models import Sede
from apps_sirae.tipos_mercado.models import TipoMercado
from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.usuarios.models import Usuario


class ConfiguracionSedeIntegracionHU4HU5Tests(TestCase):
    """Verifica compatibilidad entre configuración de sede/jornada/grados y HU 4 / HU 5."""

    def setUp(self):
        self.client = APIClient()
        self.rol_admin, _ = Rol.objects.get_or_create(nombre=Rol.NombreRol.ADMINISTRADOR)
        self.rol_supervisor, _ = Rol.objects.get_or_create(nombre=Rol.NombreRol.SUPERVISOR)

        self.institucion = Institucion.objects.create(nombre_institucion='IE Integración', nit='900777888')
        self.sede = Sede.objects.create(
            id_institucion=self.institucion,
            nombre_sede='Sede Integración',
            estado='ACTIVO',
        )

        self.admin = Usuario.objects.create_user(
            correo='admin-integracion@test.com',
            nombre='Ana',
            apellido='Admin',
            password='Password123!',
            numero_documento='ADM777',
            rol=self.rol_admin,
            id_institucion=self.institucion,
        )
        self.supervisor = Usuario.objects.create_user(
            correo='sup-integracion@test.com',
            nombre='Luis',
            apellido='Supervisor',
            password='Password123!',
            numero_documento='SUP777',
            rol=self.rol_supervisor,
        )
        SupervisorInstitucion.objects.create(
            id_supervisor=self.supervisor,
            id_institucion=self.institucion,
        )

        self.jornada_am = Jornada.objects.create(nombre_jornada='Mañana')
        self.jornada_pm = Jornada.objects.create(nombre_jornada='Tarde')
        # Jornada PM previa sin uso para ejercitar el retiro (retiradas + Q) al guardar solo AM.
        SedeJornada.objects.create(id_sede=self.sede, id_jornada=self.jornada_pm, cupos=0)

        self.contrato = Contrato.objects.create(
            numero_cor='CTR-INT-001',
            estado='Activo',
            id_institucion=self.institucion,
            id_sede=self.sede,
            id_jornada=self.jornada_am,
            id_usuario_supervisor=self.supervisor,
            cupos=100,
            periodicidad_perecederos='SEMANAL',
            dias_cobertura_perecederos=5,
            periodicidad_no_perecederos='MENSUAL',
            dias_cobertura_no_perecederos=20,
        )

        self.grupo = GrupoGramaje.objects.create(nombre='Primaria', nivel_educativo='PRIMARIA')
        self.grado_primero = Grados.objects.create(
            nombre_grado='Primero',
            id_grupo_gramaje=self.grupo,
            nivel_educativo='PRIMARIA',
            estado='ACTIVO',
        )
        self.grado_segundo = Grados.objects.create(
            nombre_grado='Segundo',
            id_grupo_gramaje=self.grupo,
            nivel_educativo='PRIMARIA',
            estado='ACTIVO',
        )

        self.u_g = UnidadMedida.objects.create(
            nombre='Gramo', abreviatura='g', tipo_magnitud='MASA', factor_conversion_base='1'
        )
        self.u_kg = UnidadMedida.objects.create(
            nombre='Kilogramo', abreviatura='Kg', tipo_magnitud='MASA', factor_conversion_base='1000'
        )
        self.cat = CategoriaInventario.objects.create(nombre_categoria='Granos')
        self.tm_no_per = TipoMercado.objects.create(nombre_tipo='No perecedero')
        self.arroz = Ingrediente.objects.create(
            nombre_ingrediente='Arroz',
            id_categoria_inventario=self.cat,
            id_unidad_medida=self.u_kg,
            tipo_conservacion='no_perecedero',
            id_tipo_mercado=self.tm_no_per,
        )

        Gramage.objects.create(
            id_ingrediente=self.arroz,
            id_grado=self.grado_primero,
            id_unidad_medida=self.u_g,
            cantidad_gramaje=Decimal('50.000'),
            estado='ACTIVO',
        )
        Gramage.objects.create(
            id_ingrediente=self.arroz,
            id_grado=self.grado_segundo,
            id_unidad_medida=self.u_g,
            cantidad_gramaje=Decimal('100.000'),
            estado='ACTIVO',
        )

        menu = Menu.objects.create(
            id_jornada=self.jornada_am,
            fecha='2026-11-11',
            ninos_presentes=40,
            estado='ACTIVO',
            informacion_nutricional='Menú integración',
            id_contrato=self.contrato.id_contrato,
        )
        plato = Plato.objects.create(nombre_plato='Arroz Estándar', componente='Cereal')
        DetallePlato.objects.create(id_menu=menu.id_menu, id_plato=plato, porcion_por_nino='100.00')
        RecetaComponente.objects.create(
            id_plato=plato,
            id_ingrediente=self.arroz,
            cantidad='80.00',
            base_cantidad='POR_NINO',
        )

    def test_guardar_configuracion_sede_e_impacto_en_alcance_y_abastecimiento(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            f'/api/sedes/{self.sede.id_sede}/configuracion/',
            {
                'jornadas': [
                    {
                        'id_jornada': self.jornada_am.id_jornada,
                        'cupos': 100,
                        'grados': [
                            {'id_grado': self.grado_primero.id_grado, 'cupos': 40},
                            {'id_grado': self.grado_segundo.id_grado, 'cupos': 60},
                        ],
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(
            SedeJornada.objects.filter(id_sede=self.sede, id_jornada=self.jornada_pm).exists()
        )

        sj = SedeJornada.objects.get(id_sede=self.sede, id_jornada=self.jornada_am)
        self.assertEqual(sj.grados_atendidos.filter(estado='ACTIVO').count(), 2)

        # HU 4: consulta de alcance refleja ambos grados configurados.
        resp_hu4 = self.client.get(f'/api/gramage/consultar-por-alcance/?id_sede={self.sede.id_sede}')
        self.assertEqual(resp_hu4.status_code, 200)
        self.assertEqual(len(resp_hu4.data['sede_jornadas']), 1)
        self.assertEqual(resp_hu4.data['sede_jornadas'][0]['total_grados'], 2)

        # HU 5: supervisor calcula mercado consolidando 40 + 60 = 100 cupos activos.
        self.client.force_authenticate(user=self.supervisor)
        resp_hu5 = self.client.get(f'/api/entregas/calcular-mercado/?id_sede={self.sede.id_sede}')
        self.assertEqual(resp_hu5.status_code, 200)
        self.assertEqual(resp_hu5.data['total_cupos'], 100)

        # Al reducir Segundo a 0 cupos, pasa a INACTIVO y deja de contar en HU 4 y HU 5.
        self.client.force_authenticate(user=self.admin)
        resp_update = self.client.post(
            f'/api/sedes/{self.sede.id_sede}/configuracion/',
            {
                'jornadas': [
                    {
                        'id_jornada': self.jornada_am.id_jornada,
                        'cupos': 40,
                        'grados': [
                            {'id_grado': self.grado_primero.id_grado, 'cupos': 40},
                        ],
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(resp_update.status_code, 200, resp_update.data)
        rel_segundo = SedeJornadaGrado.objects.get(id_sede_jornada=sj, id_grado=self.grado_segundo)
        self.assertEqual(rel_segundo.estado, 'INACTIVO')
        self.assertEqual(rel_segundo.cupos, 0)

        resp_hu4_after = self.client.get(f'/api/gramage/consultar-por-alcance/?id_sede={self.sede.id_sede}')
        self.assertEqual(resp_hu4_after.status_code, 200)
        self.assertEqual(resp_hu4_after.data['sede_jornadas'][0]['total_grados'], 1)

        self.client.force_authenticate(user=self.supervisor)
        resp_hu5_after = self.client.get(f'/api/entregas/calcular-mercado/?id_sede={self.sede.id_sede}')
        self.assertEqual(resp_hu5_after.status_code, 200)
        self.assertEqual(resp_hu5_after.data['total_cupos'], 40)
