from rest_framework.test import APITestCase

from apps_sirae.roles.models import Rol
from apps_sirae.usuarios.models import Usuario
from .models import Notificacion


class NotificacionApiTestCase(APITestCase):

    def setUp(self):
        self.admin = self.crear_usuario(
            'admin@test.com', 'Administrador'
        )
        self.supervisor = self.crear_usuario(
            'supervisor@test.com', 'supervisor'
        )
        self.manipuladora = self.crear_usuario(
            'manipuladora@test.com', 'Manipuladora'
        )
        self.jefa = self.crear_usuario(
            'jefa@test.com', 'JefaManipuladoras'
        )
        self.otra_manipuladora = self.crear_usuario(
            'otra@test.com', 'Manipuladora'
        )

        self.notificacion = Notificacion.objects.create(
            id_usuario=self.manipuladora.id_usuario,
            id_remitente=self.supervisor.id_usuario,
            titulo='Aviso de prueba',
            mensaje='Mensaje de prueba',
        )

    def crear_usuario(self, correo, nombre_rol):
        rol, _ = Rol.objects.get_or_create(nombre=nombre_rol)
        documento = correo.split('@')[0]

        return Usuario.objects.create_user(
            correo=correo,
            nombre=documento,
            apellido='Prueba',
            password='PruebaSegura123!',
            tipo_documento='CC',
            numero_documento=documento,
            rol=rol,
        )

    def solicitar(self, metodo, ruta, usuario, data=None):
        self.client.force_authenticate(user=usuario)
        return getattr(self.client, metodo)(
            ruta,
            data=data,
            format='json',
        )

    def enviar_y_comprobar_destinatarios(
        self, remitente, destinatarios_esperados
    ):
        titulo = 'Prueba distribución de roles'

        response = self.solicitar(
            'post',
            '/api/notificaciones/enviar/',
            remitente,
            {
                'titulo': titulo,
                'mensaje': 'Comprobación de notificaciones por rol.',
            },
        )

        self.assertEqual(
            response.status_code,
            201,
            msg=str(response.data),
        )

        ids_reales = set(
            Notificacion.objects.filter(
                id_remitente=remitente.id_usuario,
                titulo=titulo,
            ).values_list('id_usuario', flat=True)
        )

        ids_esperados = {
            usuario.id_usuario
            for usuario in destinatarios_esperados
        }

        self.assertEqual(ids_reales, ids_esperados)
        self.assertEqual(
            response.data['cantidad_destinatarios'],
            len(ids_esperados),
        )

    def test_lista_solo_muestra_notificaciones_propias(self):
        Notificacion.objects.create(
            id_usuario=self.otra_manipuladora.id_usuario,
            titulo='Aviso privado',
            mensaje='Mensaje de otra persona.',
        )

        response = self.solicitar(
            'get',
            '/api/notificaciones/',
            self.manipuladora,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['id_usuario'],
            self.manipuladora.id_usuario,
        )

    def test_consulta_no_leidas(self):
        response = self.solicitar(
            'get',
            '/api/notificaciones/no-leidas/',
            self.manipuladora,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['cantidad'], 1)
        self.assertEqual(len(response.data['resultados']), 1)

    def test_marcar_notificacion_propia_como_leida(self):
        response = self.solicitar(
            'post',
            (
                f'/api/notificaciones/'
                f'{self.notificacion.id_notificacion}/marcar-leida/'
            ),
            self.manipuladora,
        )

        self.assertEqual(response.status_code, 200)
        self.notificacion.refresh_from_db()
        self.assertTrue(self.notificacion.leida)

    def test_no_puede_marcar_notificacion_ajena(self):
        response = self.solicitar(
            'post',
            (
                f'/api/notificaciones/'
                f'{self.notificacion.id_notificacion}/marcar-leida/'
            ),
            self.otra_manipuladora,
        )

        self.assertEqual(response.status_code, 404)
        self.notificacion.refresh_from_db()
        self.assertFalse(self.notificacion.leida)

    def test_endpoint_generico_no_permite_crear(self):
        response = self.solicitar(
            'post',
            '/api/notificaciones/',
            self.supervisor,
            {
                'titulo': 'Prueba',
                'mensaje': 'No debe crearse por esta ruta.',
            },
        )

        self.assertEqual(response.status_code, 405)
        self.assertIn('error', response.data)

    def test_administrador_notifica_solo_al_supervisor(self):
        self.enviar_y_comprobar_destinatarios(
            self.admin,
            [self.supervisor],
        )

    def test_supervisor_puede_elegir_administrador(self):
        response = self.solicitar(
            'post',
            '/api/notificaciones/enviar/',
            self.supervisor,
            {
                'titulo': 'Mensaje al administrador',
                'mensaje': 'Prueba de envío al administrador.',
                'id_destinatario': self.admin.id_usuario,
            },
        )

        self.assertEqual(response.status_code, 201, msg=str(response.data))
        self.assertEqual(
            set(
                Notificacion.objects.filter(
                    id_remitente=self.supervisor.id_usuario,
                    titulo='Mensaje al administrador',
                ).values_list('id_usuario', flat=True)
            ),
            {self.admin.id_usuario},
        )

    def test_supervisor_puede_elegir_jefa(self):
        response = self.solicitar(
            'post',
            '/api/notificaciones/enviar/',
            self.supervisor,
            {
                'titulo': 'Mensaje a la jefa',
                'mensaje': 'Prueba de envío a la jefa.',
                'id_destinatario': self.jefa.id_usuario,
            },
        )

        self.assertEqual(response.status_code, 201, msg=str(response.data))
        self.assertEqual(
            set(
                Notificacion.objects.filter(
                    id_remitente=self.supervisor.id_usuario,
                    titulo='Mensaje a la jefa',
                ).values_list('id_usuario', flat=True)
            ),
            {self.jefa.id_usuario},
        )

    def test_supervisor_no_puede_elegir_manipuladora(self):
        response = self.solicitar(
            'post',
            '/api/notificaciones/enviar/',
            self.supervisor,
            {
                'titulo': 'Mensaje no permitido',
                'mensaje': 'No debe llegar a la manipuladora.',
                'id_destinatario': self.manipuladora.id_usuario,
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_manipuladora_no_puede_enviar(self):
        response = self.solicitar(
            'post',
            '/api/notificaciones/enviar/',
            self.manipuladora,
            {
                'titulo': 'Mensaje no permitido',
                'mensaje': 'La manipuladora no puede enviar.',
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_jefa_notifica_a_supervisor_y_administrador(self):
        self.enviar_y_comprobar_destinatarios(
            self.jefa,
            [self.supervisor, self.admin],
        )
