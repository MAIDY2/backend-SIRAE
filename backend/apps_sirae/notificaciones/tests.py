import smtplib
import socket
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
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

    def test_destinatarios_del_supervisor_son_admin_y_jefa(self):
        response = self.solicitar(
            'get',
            '/api/notificaciones/destinatarios/',
            self.supervisor,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {destinatario['id_usuario'] for destinatario in response.data},
            {self.admin.id_usuario, self.jefa.id_usuario},
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

    def test_manipuladora_puede_enviar_solo_al_supervisor(self):
        response = self.solicitar(
            'post',
            '/api/notificaciones/enviar/',
            self.manipuladora,
            {
                'titulo': 'Mensaje al supervisor',
                'mensaje': 'La manipuladora solicita apoyo.',
                'id_destinatario': self.supervisor.id_usuario,
            },
        )

        self.assertEqual(response.status_code, 201, msg=str(response.data))
        self.assertTrue(
            Notificacion.objects.filter(
                id_usuario=self.supervisor.id_usuario,
                id_remitente=self.manipuladora.id_usuario,
                titulo='Mensaje al supervisor',
            ).exists()
        )

    def test_manipuladora_no_puede_enviar_al_administrador(self):
        response = self.solicitar(
            'post',
            '/api/notificaciones/enviar/',
            self.manipuladora,
            {
                'titulo': 'Mensaje no permitido',
                'mensaje': 'La manipuladora no puede escribir al administrador.',
                'id_destinatario': self.admin.id_usuario,
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_supervisor_puede_responder_a_manipuladora_que_le_escribio(self):
        Notificacion.objects.create(
            id_usuario=self.supervisor.id_usuario,
            id_remitente=self.manipuladora.id_usuario,
            titulo='Solicitud de apoyo',
            mensaje='Necesito ayuda.',
        )

        destinatarios = self.solicitar(
            'get',
            '/api/notificaciones/destinatarios/',
            self.supervisor,
        )
        self.assertEqual(destinatarios.status_code, 200)
        ids_destinatarios = {
            destinatario['id_usuario'] for destinatario in destinatarios.data
        }
        self.assertIn(self.manipuladora.id_usuario, ids_destinatarios)
        self.assertNotIn(self.otra_manipuladora.id_usuario, ids_destinatarios)

        response = self.solicitar(
            'post',
            '/api/notificaciones/enviar/',
            self.supervisor,
            {
                'titulo': 'Respuesta del supervisor',
                'mensaje': 'Con gusto, te apoyo.',
                'id_destinatario': self.manipuladora.id_usuario,
            },
        )

        self.assertEqual(response.status_code, 201, msg=str(response.data))
        self.assertTrue(
            Notificacion.objects.filter(
                id_usuario=self.manipuladora.id_usuario,
                id_remitente=self.supervisor.id_usuario,
                titulo='Respuesta del supervisor',
            ).exists()
        )

    def test_supervisor_no_puede_iniciar_conversacion_con_manipuladora(self):
        response = self.solicitar(
            'post',
            '/api/notificaciones/enviar/',
            self.supervisor,
            {
                'titulo': 'Mensaje no permitido',
                'mensaje': 'No puede iniciar esta conversación.',
                'id_destinatario': self.manipuladora.id_usuario,
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_jefa_notifica_a_supervisor_y_administrador(self):
        self.enviar_y_comprobar_destinatarios(
            self.jefa,
            [self.supervisor, self.admin],
        )

    def test_jefa_envia_imagen_visible_para_supervisor_y_administrador(self):
        url_imagen = 'https://res.cloudinary.com/sirae/image/upload/test.png'
        imagen = SimpleUploadedFile(
            'evidencia.png',
            b'\x89PNG\r\n\x1a\ncontenido-de-prueba',
            content_type='image/png',
        )

        self.client.force_authenticate(user=self.jefa)
        with patch(
            'apps_sirae.notificaciones.api.views.cloudinary.uploader.upload',
            return_value={'secure_url': url_imagen},
        ) as subir_imagen:
            response = self.client.post(
                '/api/notificaciones/enviar/',
                {
                    'titulo': 'Reporte con imagen',
                    'mensaje': 'Imagen enviada por la jefa.',
                    'imagen': imagen,
                },
                format='multipart',
            )

        self.assertEqual(response.status_code, 201, msg=str(response.data))
        self.assertEqual(response.data['cantidad_destinatarios'], 2)
        subir_imagen.assert_called_once()

        notificaciones = Notificacion.objects.filter(
            id_remitente=self.jefa.id_usuario,
            titulo='Reporte con imagen',
        )
        self.assertEqual(
            set(notificaciones.values_list('id_usuario', flat=True)),
            {self.supervisor.id_usuario, self.admin.id_usuario},
        )
        self.assertEqual(
            set(notificaciones.values_list('imagen_url', flat=True)),
            {url_imagen},
        )

        for destinatario in (self.supervisor, self.admin):
            self.client.force_authenticate(user=destinatario)
            respuesta_lista = self.client.get('/api/notificaciones/')

            self.assertEqual(respuesta_lista.status_code, 200)
            reporte = next(
                item
                for item in respuesta_lista.data
                if item['titulo'] == 'Reporte con imagen'
            )
            self.assertEqual(reporte['imagen_url'], url_imagen)

    def test_manipuladora_envia_imagen_al_supervisor(self):
        url_imagen = 'https://res.cloudinary.com/sirae/image/upload/test.png'
        imagen = SimpleUploadedFile(
            'evidencia.png',
            b'\x89PNG\r\n\x1a\ncontenido-de-prueba',
            content_type='image/png',
        )

        self.client.force_authenticate(user=self.manipuladora)
        with patch(
            'apps_sirae.notificaciones.api.views.cloudinary.uploader.upload',
            return_value={'secure_url': url_imagen},
        ):
            response = self.client.post(
                '/api/notificaciones/enviar/',
                {
                    'titulo': 'Reporte de manipuladora',
                    'mensaje': 'Adjunto evidencia.',
                    'id_destinatario': self.supervisor.id_usuario,
                    'imagen': imagen,
                },
                format='multipart',
            )

        self.assertEqual(response.status_code, 201, msg=str(response.data))
        notificacion = Notificacion.objects.get(
            id_usuario=self.supervisor.id_usuario,
            id_remitente=self.manipuladora.id_usuario,
            titulo='Reporte de manipuladora',
        )
        self.assertEqual(notificacion.imagen_url, url_imagen)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST_USER='pruebas@sirae-pae.edu.co',
        EMAIL_HOST_PASSWORD='passwordseguro123',
    )
    @patch('apps_sirae.notificaciones.services.send_mail')
    def test_envio_notificacion_dispara_correo_con_asunto_y_cuerpo(self, mock_send):
        mock_send.return_value = 1
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            '/api/notificaciones/enviar/',
            {
                'titulo': 'Convocatoria Comité PAE',
                'mensaje': 'Reunión ordinaria el próximo lunes a las 8am.',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(mock_send.called)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST_USER='pruebas@sirae-pae.edu.co',
        EMAIL_HOST_PASSWORD='passwordseguro123',
    )
    @patch(
        'apps_sirae.notificaciones.services.send_mail',
        side_effect=smtplib.SMTPAuthenticationError(535, b'Bad credentials'),
    )
    def test_envio_notificacion_no_falla_si_smtp_genera_error_de_autenticacion(
        self, mock_send
    ):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            '/api/notificaciones/enviar/',
            {
                'titulo': 'Aviso Importante',
                'mensaje': 'El correo fallará pero la notificación persiste.',
            },
            format='json',
        )

        # La notificación se guarda y la API responde 201 sin colapsar
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Notificacion.objects.filter(titulo='Aviso Importante').exists()
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST_USER='pruebas@sirae-pae.edu.co',
        EMAIL_HOST_PASSWORD='passwordseguro123',
    )
    @patch(
        'apps_sirae.notificaciones.services.send_mail',
        side_effect=socket.timeout('Connection timed out'),
    )
    def test_envio_notificacion_no_falla_si_smtp_genera_timeout(self, mock_send):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            '/api/notificaciones/enviar/',
            {
                'titulo': 'Aviso Timeout',
                'mensaje': 'Prueba de tolerancia a fallos por latencia de red.',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Notificacion.objects.filter(titulo='Aviso Timeout').exists()
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST_USER='pruebas@sirae-pae.edu.co',
        EMAIL_HOST_PASSWORD='passwordseguro123',
    )
    @patch('apps_sirae.notificaciones.services.send_mail')
    def test_alerta_inventario_crea_notificacion_y_envia_correo(self, mock_send):
        mock_send.return_value = 1
        self.client.force_authenticate(user=self.supervisor)

        response = self.client.post(
            '/api/notificaciones/alerta-inventario/',
            {
                'ingrediente': 'Arroz Blanco',
                'sede': 'Sede Principal Los Pinos',
                'stock_actual': 1.5,
                'stock_minimo': 10.0,
                'unidad': 'Kg',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Notificacion.objects.filter(
                titulo__icontains='Arroz Blanco'
            ).exists()
        )
        self.assertTrue(mock_send.called)

    def test_alerta_inventario_falla_sin_campos_obligatorios(self):
        self.client.force_authenticate(user=self.supervisor)

        response = self.client.post(
            '/api/notificaciones/alerta-inventario/',
            {'ingrediente': 'Arroz Blanco'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST_USER='pruebas@sirae-pae.edu.co',
        EMAIL_HOST_PASSWORD='passwordseguro123',
    )
    @patch('apps_sirae.notificaciones.services.send_mail')
    def test_probar_email_endpoint_solo_admin(self, mock_send):
        mock_send.return_value = 1

        # Supervisor no debe poder probar el endpoint de diagnóstico
        self.client.force_authenticate(user=self.supervisor)
        resp_sup = self.client.post(
            '/api/notificaciones/probar-email/',
            {'email': 'test@gmail.com'},
            format='json',
        )
        self.assertEqual(resp_sup.status_code, 403)

        # Admin sí puede probarlo
        self.client.force_authenticate(user=self.admin)
        resp_admin = self.client.post(
            '/api/notificaciones/probar-email/',
            {'email': 'destino@gmail.com'},
            format='json',
        )
        self.assertEqual(resp_admin.status_code, 200)
        self.assertTrue(resp_admin.data['resultado']['exito'])
