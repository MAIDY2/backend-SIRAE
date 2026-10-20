from django.test import TestCase

from apps_sirae.roles.models import Rol
from apps_sirae.usuarios.models import Usuario


class UsuarioRoleMethodTests(TestCase):
    def create_user_with_role(self, role_name):
        role = Rol.objects.create(nombre=role_name)
        return Usuario.objects.create_user(
            correo=f'{role_name.lower().replace(" ", ".")}@example.com',
            nombre='Test',
            apellido='User',
            password='secure-password-42',
            tipo_documento='CC',
            numero_documento=f'DOC-{Rol.objects.count()}',
            rol=role,
        )

    def test_supervisor_role_maps_to_coordinator_permissions(self):
        usuario = self.create_user_with_role(Rol.NombreRol.SUPERVISOR)

        self.assertTrue(usuario.es_supervisor())
        self.assertFalse(usuario.es_administrador())

    def test_legacy_coordinator_role_maps_to_supervisor_permissions(self):
        usuario = self.create_user_with_role('Coordinador PAE')

        self.assertTrue(usuario.es_supervisor())

    def test_other_roles_do_not_receive_supervisor_permissions(self):
        usuario = self.create_user_with_role(Rol.NombreRol.JEFA_MANIPULADORAS)

        self.assertFalse(usuario.es_supervisor())
        self.assertTrue(usuario.es_jefa_manipuladoras())
