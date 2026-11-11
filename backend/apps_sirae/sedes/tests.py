from django.test import TestCase
from rest_framework.test import APIClient

from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.contratos_seccion_menu.models import ContratoSeccionMenu
from apps_sirae.instituciones.models import Institucion
from apps_sirae.jornadas.models import Jornada
from apps_sirae.roles.models import Rol
from apps_sirae.secciones_menu.models import SeccionMenu
from apps_sirae.sede_jornada.models import SedeJornada
from apps_sirae.usuarios.models import Usuario

from .models import Sede


class ConsultaSedesAdministradorTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.institucion = Institucion.objects.create(
            nombre_institucion='Institución Administrador',
            nit='900000001',
        )
        self.otra_institucion = Institucion.objects.create(
            nombre_institucion='Otra Institución',
            nit='900000002',
        )
        self.rol_admin, _ = Rol.objects.get_or_create(
            nombre=Rol.NombreRol.ADMINISTRADOR,
        )
        self.administrador = Usuario.objects.create_user(
            correo='admin-sedes@example.com',
            nombre='Admin',
            apellido='Sedes',
            password='test-password',
            tipo_documento='CC',
            numero_documento='ADMINSEDES001',
            rol=self.rol_admin,
            id_institucion=self.institucion,
        )
        self.sede = Sede.objects.create(
            id_institucion=self.institucion,
            nombre_sede='Sede Administrada',
            codigo_dane='123456',
            direccion='Calle 1',
            telefono='3000000000',
            estado='ACTIVO',
        )
        self.sede_ajena = Sede.objects.create(
            id_institucion=self.otra_institucion,
            nombre_sede='Sede Ajena',
        )
        self.client.force_authenticate(user=self.administrador)

    def test_list_only_includes_sedes_from_assigned_institution(self):
        response = self.client.get('/api/sedes/')

        self.assertEqual(response.status_code, 200)
        sede_ids = {item['id_sede'] for item in response.data}
        self.assertEqual(sede_ids, {self.sede.id_sede})

    def test_admin_without_institution_sees_no_sedes(self):
        self.administrador.id_institucion = None
        self.administrador.save(update_fields=['id_institucion'])

        response = self.client.get('/api/sedes/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_configuration_sums_contract_cupos_and_groups_menu_sections_by_jornada(self):
        jornada = Jornada.objects.create(nombre_jornada='Mañana')
        SedeJornada.objects.create(id_sede=self.sede, id_jornada=jornada)
        contrato = Contrato.objects.create(
            id_institucion=self.institucion,
            id_sede=self.sede,
            id_jornada=jornada,
            cupos=35,
        )
        Contrato.objects.create(
            id_institucion=self.institucion,
            id_sede=self.sede,
            id_jornada=jornada,
            cupos=15,
        )
        seccion = SeccionMenu.objects.create(
            id_jornada=jornada,
            nombre_seccion='Almuerzo',
        )
        ContratoSeccionMenu.objects.create(
            id_contrato=contrato,
            id_seccion=seccion,
            estado='ACTIVA',
        )

        response = self.client.get(
            f'/api/sedes/{self.sede.id_sede}/configuracion/'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['cupos_totales'], 50)
        self.assertEqual(response.data['sede']['nombre_sede'], 'Sede Administrada')
        self.assertEqual(len(response.data['jornadas']), 1)
        self.assertEqual(response.data['jornadas'][0]['nombre_jornada'], 'Mañana')
        self.assertEqual(response.data['jornadas'][0]['cupos'], 50)
        self.assertEqual(
            response.data['jornadas'][0]['secciones'][0]['nombre_seccion'],
            'Almuerzo',
        )

    def test_admin_cannot_read_configuration_for_another_institutions_sede(self):
        response = self.client.get(
            f'/api/sedes/{self.sede_ajena.id_sede}/configuracion/'
        )

        self.assertEqual(response.status_code, 404)
