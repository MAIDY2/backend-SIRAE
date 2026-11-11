from types import SimpleNamespace

from django.test import TestCase

from apps_sirae.instituciones.models import (
    Institucion,
    SupervisorInstitucion,
)
from apps_sirae.instituciones.api.views import InstitucionViewSet
from apps_sirae.usuarios.models import Usuario
from apps_sirae.roles.models import Rol
from apps_sirae.contratos_pae.models import Contrato


class InstitucionViewSetTests(TestCase):

    def setUp(self):
        self.rol_supervisor = Rol.objects.create(
            nombre=Rol.NombreRol.SUPERVISOR
        )

        self.institucion_1 = Institucion.objects.create(
            nombre_institucion='Institucion de prueba 1',
            nit='TEST-001'
        )

        self.institucion_2 = Institucion.objects.create(
            nombre_institucion='Institucion de prueba 2',
            nit='TEST-002'
        )

        self.supervisor = Usuario.objects.create_user(
            correo='supervisor_prueba@sirae.test',
            nombre='Supervisor',
            apellido='Prueba',
            password='Prueba123*',
            tipo_documento='CC',
            numero_documento='TEST-SUP-001',
            rol=self.rol_supervisor
        )

    def obtener_instituciones(self, usuario):
        view = InstitucionViewSet()

        view.request = SimpleNamespace(
            user=usuario,
            query_params={}
        )

        return list(view.get_queryset())

    def test_supervisor_ve_institucion_asignada(self):
        SupervisorInstitucion.objects.create(
            id_supervisor=self.supervisor,
            id_institucion=self.institucion_1
        )

        instituciones = self.obtener_instituciones(self.supervisor)

        self.assertEqual(
            [i.id_institucion for i in instituciones],
            [self.institucion_1.id_institucion]
        )

    def test_supervisor_ve_su_institucion_directa(self):
        self.supervisor.id_institucion = self.institucion_1
        self.supervisor.save()

        instituciones = self.obtener_instituciones(self.supervisor)

        self.assertEqual(
            [i.id_institucion for i in instituciones],
            [self.institucion_1.id_institucion]
        )

    def test_supervisor_ve_institucion_de_su_contrato(self):
        Contrato.objects.create(
            id_usuario_supervisor=self.supervisor,
            id_institucion=self.institucion_2
        )

        instituciones = self.obtener_instituciones(self.supervisor)

        self.assertEqual(
            [i.id_institucion for i in instituciones],
            [self.institucion_2.id_institucion]
        )

    def test_supervisor_sin_asignaciones_no_ve_instituciones(self):
        instituciones = self.obtener_instituciones(self.supervisor)

        self.assertEqual(instituciones, [])