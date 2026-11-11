from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

from apps_sirae.roles.models import (
    Rol,
    RolPermiso,
    AuditoriaPermisoRol,
    MATRIZ_MODULOS_SISTEMA,
    PERMISOS_CRITICOS_SUPERADMIN
)
from apps_sirae.usuarios.models import Usuario


class ConsultaYAdministracionPermisosRolesTests(TestCase):
    """
    Suite integral de pruebas unitarias y de integración para la auditoría
    y verificación de los 11 Criterios de Configuración y Administración
    de Permisos de Roles en SIRAE PAE.
    """

    def setUp(self):
        self.client = APIClient()

        # Asegurar catálogo estándar de roles
        self.rol_super = Rol.objects.get_or_create(
            nombre=Rol.NombreRol.SUPER_ADMINISTRADOR,
            defaults={'descripcion': 'Super administrador con acceso total al sistema.'}
        )[0]
        self.rol_admin = Rol.objects.get_or_create(
            nombre=Rol.NombreRol.ADMINISTRADOR,
            defaults={'descripcion': 'Administrador institucional responsable del comedor.'}
        )[0]
        self.rol_supervisor = Rol.objects.get_or_create(
            nombre=Rol.NombreRol.SUPERVISOR,
            defaults={'descripcion': 'Supervisor de interventoría técnica del PAE.'}
        )[0]
        self.rol_jefa = Rol.objects.get_or_create(
            nombre=Rol.NombreRol.JEFA_MANIPULADORAS,
            defaults={'descripcion': 'Líder operativa del equipo de manipuladoras de cocina.'}
        )[0]
        self.rol_manipuladora = Rol.objects.get_or_create(
            nombre=Rol.NombreRol.MANIPULADORA,
            defaults={'descripcion': 'Manipuladora de alimentos en comedor escolar.'}
        )[0]

        # Usuarios de prueba
        self.superadmin = Usuario.objects.create_user(
            correo="superadmin@sirae.gov.co",
            nombre="Carlos",
            apellido="SuperAdmin",
            password="Super-Pass-2026!xQ",
            tipo_documento="CC",
            numero_documento="ROL0001",
            rol=self.rol_super,
            is_superuser=True,
            is_staff=True,
        )

        self.admin = Usuario.objects.create_user(
            correo="admin@sirae.edu.co",
            nombre="Patricia",
            apellido="Admin",
            password="Admin-Pass-2026!xQ",
            tipo_documento="CC",
            numero_documento="ROL0002",
            rol=self.rol_admin,
            is_active=True,
        )

        self.supervisor = Usuario.objects.create_user(
            correo="supervisor@sirae.edu.co",
            nombre="Andrés",
            apellido="Supervisor",
            password="Sup-Pass-2026!xQ",
            tipo_documento="CC",
            numero_documento="ROL0003",
            rol=self.rol_supervisor,
            is_active=True,
        )

        self.manipuladora_activa = Usuario.objects.create_user(
            correo="cocinera@sirae.edu.co",
            nombre="Rosa",
            apellido="Gómez",
            password="Cocinera-Pass-2026!xQ",
            tipo_documento="CC",
            numero_documento="ROL0004",
            rol=self.rol_manipuladora,
            is_active=True,
        )

    def test_criterio_1_listado_roles_principales(self):
        """
        Criterio 1: Mostrar con claridad los roles principales definidos en SIRAE
        (Superadministrador, Supervisor, Administrador institucional).
        """
        self.client.force_authenticate(user=self.superadmin)
        resp = self.client.get("/api/roles/")
        self.assertEqual(resp.status_code, 200)

        data = resp.data.get('results', resp.data) if isinstance(resp.data, dict) else resp.data
        nombres = [r['nombre'] for r in data]
        self.assertIn('SuperAdministrador', nombres)
        self.assertIn('Administrador', nombres)
        self.assertIn('supervisor', nombres)

        for item in data:
            self.assertIn('total_usuarios_activos', item)
            self.assertIn('puede_editar_permisos', item)

    def test_criterio_2_matriz_modulos_y_funcionalidades(self):
        """
        Criterio 2: Mostrar la estructura completa de módulos y funcionalidades disponibles en el sistema.
        """
        self.client.force_authenticate(user=self.superadmin)
        resp = self.client.get("/api/roles/matriz-modulos/")
        self.assertEqual(resp.status_code, 200)

        modulos = resp.data
        self.assertIsInstance(modulos, list)
        self.assertGreaterEqual(len(modulos), 5)

        nombres_modulos = [m['modulo'] for m in modulos]
        self.assertIn('Usuarios y Roles', nombres_modulos)
        self.assertIn('Instituciones y Sedes', nombres_modulos)
        self.assertIn('Contratos PAE', nombres_modulos)
        self.assertIn('Inventario y Almacén', nombres_modulos)

        # Verificar estructura de permisos dentro de cada módulo
        primer_modulo = modulos[0]
        self.assertIn('nombre_modulo', primer_modulo)
        self.assertIn('descripcion', primer_modulo)
        self.assertIn('permisos', primer_modulo)
        self.assertIsInstance(primer_modulo['permisos'], list)
        self.assertGreater(len(primer_modulo['permisos']), 0)

        perm = primer_modulo['permisos'][0]
        self.assertIn('codigo', perm)
        self.assertIn('nombre', perm)
        self.assertIn('descripcion', perm)

    def test_criterio_3_consulta_permisos_por_rol(self):
        """
        Criterio 3: Permitir consultar de forma granular los permisos asociados a cada rol específico.
        """
        self.client.force_authenticate(user=self.superadmin)
        resp = self.client.get(f"/api/roles/{self.rol_supervisor.id_rol}/permisos/")
        self.assertEqual(resp.status_code, 200)

        permisos = resp.data
        self.assertIsInstance(permisos, list)
        self.assertGreater(len(permisos), 0)

        codigos = [p['codigo'] for p in permisos]
        self.assertIn('supervision_instituciones_asignadas', codigos)
        self.assertIn('entregas_pae_registro_verificacion', codigos)

    def test_criterio_4_operacion_autorizada_de_modificacion_restringida_a_superadmin(self):
        """
        Criterio 4: Permitir modificar los permisos asignados únicamente mediante operaciones
        fuertemente autorizadas y controladas en backend (restringido a Superadministrador).
        """
        # Usuario Administrador institucional intenta modificar permisos -> 403 Forbidden
        self.client.force_authenticate(user=self.admin)
        payload = {'permisos': ['asistencia_diaria_registro']}
        resp_admin = self.client.post(f"/api/roles/{self.rol_jefa.id_rol}/asignar-permisos/", payload, format='json')
        self.assertEqual(resp_admin.status_code, 403)
        self.assertIn("Solo el Super Administrador está autorizado", str(resp_admin.data))

        # Usuario anónimo -> 401 Unauthorized
        self.client.logout()
        resp_anon = self.client.post(f"/api/roles/{self.rol_jefa.id_rol}/asignar-permisos/", payload, format='json')
        self.assertEqual(resp_anon.status_code, 401)

    def test_criterio_5_prevencion_de_escalada_de_privilegios(self):
        """
        Criterio 5: Evitar terminantemente que un rol o usuario adquiera o administre
        permisos superiores a los autorizados para su propia jerarquía.
        Intentar asignar un permiso crítico del Superadministrador a un rol subordinado
        debe ser bloqueado y auditado como INTENTO_ESCALADA_PRIVILEGIOS.
        """
        self.client.force_authenticate(user=self.superadmin)

        # Intentar otorgar permisos de gestión global al rol 'supervisor'
        payload = {
            'permisos': [
                'supervision_instituciones_asignadas',
                'usuarios_roles_total'  # Permiso crítico de Superadministrador
            ]
        }
        resp = self.client.post(f"/api/roles/{self.rol_supervisor.id_rol}/asignar-permisos/", payload, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Prevención de escalada de privilegios", str(resp.data))

        # Verificar que se registró formalmente en la auditoría
        auditoria_intento = AuditoriaPermisoRol.objects.filter(
            rol=self.rol_supervisor,
            accion='INTENTO_ESCALADA_PRIVILEGIOS'
        ).first()
        self.assertIsNotNone(auditoria_intento)
        self.assertEqual(auditoria_intento.usuario_actor, self.superadmin)
        self.assertIn('usuarios_roles_total', auditoria_intento.detalle)

    def test_criterio_6_proteccion_de_permisos_criticos_del_superadministrador(self):
        """
        Criterio 6: Blindar los permisos globales del Superadministrador para impedir
        su eliminación, alteración o revocación accidental o maliciosa.
        """
        self.client.force_authenticate(user=self.superadmin)

        # Intentar recortar o vaciar los permisos del rol SuperAdministrador
        payload = {'permisos': ['auditoria_operativa_lectura']}  # Falta 'usuarios_roles_total', 'contratos_gestion_total', etc.
        resp = self.client.post(f"/api/roles/{self.rol_super.id_rol}/asignar-permisos/", payload, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Protección de seguridad crítica", str(resp.data))
        self.assertIn("Los permisos globales del Superadministrador están blindados", str(resp.data))

    def test_criterio_7_salvaguarda_de_administracion_global(self):
        """
        Criterio 7: Validar rigurosamente que cualquier cambio de permisos o roles
        no deje al sistema completamente desatendido o sin un usuario administrador global autorizado activo.
        """
        # Desactivamos temporalmente al único Superadmin
        self.superadmin.is_active = False
        self.superadmin.save()

        # Creamos otro superadmin temporal para hacer el request
        otro_super = Usuario.objects.create_user(
            correo="otro_super@sirae.gov.co",
            nombre="Temporal",
            apellido="Super",
            password="TempPass2026!xQ",
            tipo_documento="CC",
            numero_documento="ROL0999",
            rol=self.rol_admin,  # No tiene rol SuperAdministrador
            is_superuser=True,
            is_staff=True,
        )

        self.client.force_authenticate(user=otro_super)
        payload = {'permisos': ['cocina_recetas_pasos']}
        resp = self.client.post(f"/api/roles/{self.rol_manipuladora.id_rol}/asignar-permisos/", payload, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Salvaguarda de seguridad", str(resp.data))
        self.assertIn("no cuenta con un usuario Superadministrador activo", str(resp.data))

        # Restauramos superadmin
        self.superadmin.is_active = True
        self.superadmin.save()

    def test_criterio_8_y_10_aplicacion_inmediata_y_trazabilidad_auditoria(self):
        """
        Criterio 8: Aplicar los cambios de permisos de forma efectiva a las nuevas solicitudes tras la actualización.
        Criterio 10: Registrar detalladamente en la bitácora del sistema todos los cambios realizados.
        """
        self.client.force_authenticate(user=self.superadmin)

        nuevos_permisos_jefa = [
            'asistencia_diaria_registro',
            'menu_diario_seleccion'
        ]
        payload = {'permisos': nuevos_permisos_jefa}

        resp = self.client.post(f"/api/roles/{self.rol_jefa.id_rol}/asignar-permisos/", payload, format='json')
        self.assertEqual(resp.status_code, 200)

        # Criterio 8: La consulta posterior debe reflejar de inmediato los permisos persistidos
        self.rol_jefa.refresh_from_db()
        permisos_actuales = [p['codigo'] for p in self.rol_jefa.permisos]
        self.assertEqual(set(permisos_actuales), set(nuevos_permisos_jefa))

        # Criterio 10: Verificar registro en la bitácora de auditoría
        auditoria = AuditoriaPermisoRol.objects.filter(
            rol=self.rol_jefa,
            accion='MODIFICACION_PERMISOS'
        ).first()
        self.assertIsNotNone(auditoria)
        self.assertEqual(auditoria.usuario_actor, self.superadmin)
        self.assertEqual(set(auditoria.permisos_nuevos), set(nuevos_permisos_jefa))
        self.assertIn("Actualización de permisos del rol", auditoria.detalle)

        # Consultar endpoint de auditoría del rol
        resp_aud = self.client.get(f"/api/roles/{self.rol_jefa.id_rol}/auditoria/")
        self.assertEqual(resp_aud.status_code, 200)
        self.assertGreater(len(resp_aud.data), 0)
        self.assertEqual(resp_aud.data[0]['actor_correo'], self.superadmin.correo)

    def test_criterio_9_revocacion_por_modificaciones_criticas(self):
        """
        Criterio 9: Revocar o forzar la actualización de las sesiones y autorizaciones
        activas que se vean afectadas directamente por modificaciones de permisos.
        """
        # Emitir un token JWT activo para la manipuladora activa
        refresh = RefreshToken.for_user(self.manipuladora_activa)
        access_token_str = str(refresh.access_token)

        # Asegurar token sobresaliente
        outstanding = OutstandingToken.objects.filter(user=self.manipuladora_activa).first()
        self.assertIsNotNone(outstanding)

        # El Superadmin modifica los permisos del rol 'Manipuladora'
        self.client.force_authenticate(user=self.superadmin)
        payload = {'permisos': ['cocina_recetas_pasos']}
        resp = self.client.post(f"/api/roles/{self.rol_manipuladora.id_rol}/asignar-permisos/", payload, format='json')
        self.assertEqual(resp.status_code, 200)

        # Verificar que el token de la manipuladora fue revocado en lista negra (BlacklistedToken)
        self.assertTrue(
            BlacklistedToken.objects.filter(token=outstanding).exists(),
            "El token activo de la usuaria afectada debe ser añadido a la lista negra tras la modificación de permisos."
        )

    def test_criterio_11_proteccion_de_roles_con_usuarios_activos(self):
        """
        Criterio 11: Impedir la eliminación o desactivación de roles que posean usuarios
        asociados activos a menos que se ejecute un proceso controlado de reasignación de personal.
        """
        self.client.force_authenticate(user=self.superadmin)

        # El rol 'Manipuladora' tiene a 'self.manipuladora_activa' (is_active=True)
        resp_del = self.client.delete(f"/api/roles/{self.rol_manipuladora.id_rol}/")
        self.assertEqual(resp_del.status_code, 400)
        self.assertIn("tiene 1 usuario(s) activo(s) asociado(s)", str(resp_del.data))
        self.assertIn("Debe reasignar el personal previamente", str(resp_del.data))

        # Verificar que el rol no fue eliminado
        self.assertTrue(Rol.objects.filter(id_rol=self.rol_manipuladora.id_rol).exists())
