from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps_sirae.roles.models import Rol
from apps_sirae.usuarios.models import Usuario
from apps_sirae.mensajes.models import Mensaje
from apps_sirae.mensajes.permissions import MENSAJE_ERROR_PERMISOS


class MensajesPermisosYFuncionalidadTestCase(APITestCase):

    @classmethod
    def setUpTestData(cls):
        # Crear roles
        cls.rol_superadmin, _ = Rol.objects.get_or_create(
            nombre=Rol.NombreRol.SUPER_ADMINISTRADOR,
            defaults={'descripcion': 'Super Administrador'}
        )
        cls.rol_admin, _ = Rol.objects.get_or_create(
            nombre=Rol.NombreRol.ADMINISTRADOR,
            defaults={'descripcion': 'Administrador'}
        )
        cls.rol_supervisor, _ = Rol.objects.get_or_create(
            nombre=Rol.NombreRol.SUPERVISOR,
            defaults={'descripcion': 'Supervisor'}
        )
        cls.rol_jefa, _ = Rol.objects.get_or_create(
            nombre=Rol.NombreRol.JEFA_MANIPULADORAS,
            defaults={'descripcion': 'Jefa de Manipuladoras'}
        )
        cls.rol_manipuladora, _ = Rol.objects.get_or_create(
            nombre=Rol.NombreRol.MANIPULADORA,
            defaults={'descripcion': 'Manipuladora'}
        )

        # Crear usuarios para cada rol
        cls.u_superadmin = Usuario.objects.create_user(
            correo='superadmin@sirae.com',
            nombre='Super',
            apellido='Admin',
            password='Password123!',
            rol=cls.rol_superadmin,
            tipo_documento='CC',
            numero_documento='1001'
        )

        cls.u_admin = Usuario.objects.create_user(
            correo='admin@sirae.com',
            nombre='Admin',
            apellido='General',
            password='Password123!',
            rol=cls.rol_admin,
            tipo_documento='CC',
            numero_documento='1002'
        )

        cls.u_supervisor = Usuario.objects.create_user(
            correo='supervisor@sirae.com',
            nombre='Supervisor',
            apellido='Campo',
            password='Password123!',
            rol=cls.rol_supervisor,
            tipo_documento='CC',
            numero_documento='1003'
        )

        cls.u_jefa = Usuario.objects.create_user(
            correo='jefa@sirae.com',
            nombre='Jefa',
            apellido='Cocina',
            password='Password123!',
            rol=cls.rol_jefa,
            tipo_documento='CC',
            numero_documento='1004'
        )

        cls.u_manipuladora = Usuario.objects.create_user(
            correo='manipuladora@sirae.com',
            nombre='Manipuladora',
            apellido='Base',
            password='Password123!',
            rol=cls.rol_manipuladora,
            tipo_documento='CC',
            numero_documento='1005'
        )

    def autenticar(self, usuario):
        token = str(RefreshToken.for_user(usuario).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_ca01_jefa_a_supervisor_y_viceversa(self):
        """CA-01: Manipuladora Jefe <-> Supervisor bidireccional permitido"""
        # Jefa -> Supervisor
        self.autenticar(self.u_jefa)
        url = reverse('mensajes-enviar')
        res1 = self.client.post(url, {
            'destinatario': self.u_supervisor.id_usuario,
            'contenido_texto': 'Hola Supervisor, reporte de hoy listo.'
        })
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data['contenido_texto'], 'Hola Supervisor, reporte de hoy listo.')

        # Supervisor -> Jefa
        self.autenticar(self.u_supervisor)
        res2 = self.client.post(url, {
            'destinatario': self.u_jefa.id_usuario,
            'contenido_texto': 'Enterado Jefa, proceda.'
        })
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)

    def test_ca02_supervisor_a_admin_y_superadmin_y_viceversa(self):
        """CA-02: Supervisor <-> Administrador / Superadministrador bidireccional permitido"""
        url = reverse('mensajes-enviar')

        # Supervisor -> Admin
        self.autenticar(self.u_supervisor)
        res1 = self.client.post(url, {
            'destinatario': self.u_admin.id_usuario,
            'contenido_texto': 'Auditoría completada.'
        })
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Admin -> Supervisor
        self.autenticar(self.u_admin)
        res2 = self.client.post(url, {
            'destinatario': self.u_supervisor.id_usuario,
            'contenido_texto': 'Recibido informe de auditoría.'
        })
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)

        # Supervisor -> Superadmin
        self.autenticar(self.u_supervisor)
        res3 = self.client.post(url, {
            'destinatario': self.u_superadmin.id_usuario,
            'contenido_texto': 'Alerta en circuito norte.'
        })
        self.assertEqual(res3.status_code, status.HTTP_201_CREATED)

        # Superadmin -> Supervisor
        self.autenticar(self.u_superadmin)
        res4 = self.client.post(url, {
            'destinatario': self.u_supervisor.id_usuario,
            'contenido_texto': 'Revisando alerta del circuito.'
        })
        self.assertEqual(res4.status_code, status.HTTP_201_CREATED)

    def test_ca03_manipuladora_a_jefa(self):
        """CA-03: Manipuladora Base -> Manipuladora Jefe permitido"""
        self.autenticar(self.u_manipuladora)
        url = reverse('mensajes-enviar')
        res = self.client.post(url, {
            'destinatario': self.u_jefa.id_usuario,
            'contenido_texto': 'Jefa, se terminó el inventario de sal.'
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_ca04_jefa_a_manipuladora(self):
        """CA-04: Manipuladora Jefe -> Manipuladora Base permitido"""
        self.autenticar(self.u_jefa)
        url = reverse('mensajes-enviar')
        res = self.client.post(url, {
            'destinatario': self.u_manipuladora.id_usuario,
            'contenido_texto': 'Favor verificar fecha de vencimiento de los lácteos.'
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_ca05_bloqueo_envios_no_autorizados(self):
        """CA-05: Bloqueo de envíos fuera de la matriz con 403 Forbidden y mensaje exacto"""
        url = reverse('mensajes-enviar')

        # 1. Manipuladora Base -> Supervisor (NO AUTORIZADO)
        self.autenticar(self.u_manipuladora)
        res1 = self.client.post(url, {
            'destinatario': self.u_supervisor.id_usuario,
            'contenido_texto': 'Hola Supervisor directo.'
        })
        self.assertEqual(res1.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('error', res1.data)
        self.assertEqual(res1.data['error'], MENSAJE_ERROR_PERMISOS)

        # 2. Manipuladora Base -> Administrador (NO AUTORIZADO)
        res2 = self.client.post(url, {
            'destinatario': self.u_admin.id_usuario,
            'contenido_texto': 'Hola Admin.'
        })
        self.assertEqual(res2.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res2.data['error'], MENSAJE_ERROR_PERMISOS)

        # 3. Administrador -> Manipuladora Base (NO AUTORIZADO)
        self.autenticar(self.u_admin)
        res3 = self.client.post(url, {
            'destinatario': self.u_manipuladora.id_usuario,
            'contenido_texto': 'Aviso a manipuladora.'
        })
        self.assertEqual(res3.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res3.data['error'], MENSAJE_ERROR_PERMISOS)

        # 4. Supervisor -> Manipuladora Base (NO AUTORIZADO)
        self.autenticar(self.u_supervisor)
        res4 = self.client.post(url, {
            'destinatario': self.u_manipuladora.id_usuario,
            'contenido_texto': 'Supervisor a base.'
        })
        self.assertEqual(res4.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res4.data['error'], MENSAJE_ERROR_PERMISOS)

    def test_ca06_estructura_del_mensaje(self):
        """CA-06: Estructura del registro de mensaje en BD (remitente, destinatario, texto, imagen, fecha_envio, leido)"""
        self.autenticar(self.u_jefa)
        url = reverse('mensajes-enviar')
        res = self.client.post(url, {
            'destinatario': self.u_supervisor.id_usuario,
            'contenido_texto': 'Mensaje con estructura.'
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        msg_id = res.data['id_mensaje']

        mensaje_db = Mensaje.objects.get(id_mensaje=msg_id)
        self.assertEqual(mensaje_db.remitente_id, self.u_jefa.id_usuario)
        self.assertEqual(mensaje_db.destinatario_id, self.u_supervisor.id_usuario)
        self.assertEqual(mensaje_db.contenido_texto, 'Mensaje con estructura.')
        self.assertFalse(mensaje_db.leido)
        self.assertIsNotNone(mensaje_db.fecha_envio)

    @patch('apps_sirae.mensajes.api.views.cloudinary.uploader.upload')
    def test_ca07_soporte_multimedia_cloudinary(self, mock_upload):
        """CA-07: Procesar imagen adjunta (.jpg, .jpeg, .png, max 5MB), subir a Cloudinary y guardar imagen_url"""
        mock_upload.return_value = {
            'secure_url': 'https://res.cloudinary.com/sirae/image/upload/v1/sirae_mensajes/evidencia.jpg'
        }

        self.autenticar(self.u_jefa)
        url = reverse('mensajes-enviar')

        # Archivo JPG simulado de 100 bytes
        imagen_valida = SimpleUploadedFile(
            'evidencia.jpg',
            b'fake image data bytes',
            content_type='image/jpeg'
        )

        res = self.client.post(url, {
            'destinatario': self.u_supervisor.id_usuario,
            'contenido_texto': 'Evidencia de cocción adjunta',
            'imagen': imagen_valida
        }, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            res.data['imagen_url'],
            'https://res.cloudinary.com/sirae/image/upload/v1/sirae_mensajes/evidencia.jpg'
        )
        mock_upload.assert_called_once()

    def test_ca07_rechazo_imagen_demasiado_grande(self):
        """CA-07: Rechazo de imagen superior a 5MB"""
        self.autenticar(self.u_jefa)
        url = reverse('mensajes-enviar')

        # Imagen simulada de más de 5MB
        imagen_pesada = SimpleUploadedFile(
            'pesada.png',
            b'0' * (5 * 1024 * 1024 + 10),
            content_type='image/png'
        )

        res = self.client.post(url, {
            'destinatario': self.u_supervisor.id_usuario,
            'imagen': imagen_pesada
        }, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('5MB', res.data['error'])

    def test_ca07_rechazo_formato_no_permitido(self):
        """CA-07: Rechazo de extensiones diferentes a .jpg, .jpeg, .png"""
        self.autenticar(self.u_jefa)
        url = reverse('mensajes-enviar')

        archivo_invalido = SimpleUploadedFile(
            'documento.pdf',
            b'some pdf content',
            content_type='application/pdf'
        )

        res = self.client.post(url, {
            'destinatario': self.u_supervisor.id_usuario,
            'imagen': archivo_invalido
        }, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ca08_y_ca09_historial_y_marcado_automatico_lectura(self):
        """CA-08 (Orden cronológico tipo chat) y CA-09 (Marcado automático leido=False -> True al consultar)"""
        # Crear 2 mensajes de Jefa a Supervisor
        m1 = Mensaje.objects.create(
            remitente=self.u_jefa,
            destinatario=self.u_supervisor,
            contenido_texto='Primer mensaje',
            leido=False
        )
        m2 = Mensaje.objects.create(
            remitente=self.u_jefa,
            destinatario=self.u_supervisor,
            contenido_texto='Segundo mensaje',
            leido=False
        )

        # Supervisor responde
        m3 = Mensaje.objects.create(
            remitente=self.u_supervisor,
            destinatario=self.u_jefa,
            contenido_texto='Respuesta supervisor',
            leido=False
        )

        # Supervisor consulta la conversación con Jefa
        self.autenticar(self.u_supervisor)
        url = reverse('mensajes-conversacion', kwargs={'contacto_id': self.u_jefa.id_usuario})
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        mensajes_recibidos = res.data['mensajes']
        self.assertEqual(len(mensajes_recibidos), 3)

        # CA-08: Verificar orden cronológico más antiguo primero
        self.assertEqual(mensajes_recibidos[0]['contenido_texto'], 'Primer mensaje')
        self.assertEqual(mensajes_recibidos[1]['contenido_texto'], 'Segundo mensaje')
        self.assertEqual(mensajes_recibidos[2]['contenido_texto'], 'Respuesta supervisor')

        # CA-09: Los mensajes m1 y m2 deben haber cambiado a leido = True
        m1.refresh_from_db()
        m2.refresh_from_db()
        self.assertTrue(m1.leido)
        self.assertTrue(m2.leido)

        # Pero el mensaje m3 (enviado por el supervisor a la jefa) aún no ha sido leído por la jefa
        m3.refresh_from_db()
        self.assertFalse(m3.leido)

    def test_contactos_permitidos_endpoint(self):
        """Verifica que el endpoint /contactos retorne solo los contactos permitidos por la matriz"""
        # La manipuladora solo debe ver a la Jefa de Manipuladoras
        self.autenticar(self.u_manipuladora)
        url = reverse('mensajes-contactos')
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        ids_contactos = [c['id_usuario'] for c in res.data]
        self.assertIn(self.u_jefa.id_usuario, ids_contactos)
        self.assertNotIn(self.u_supervisor.id_usuario, ids_contactos)
        self.assertNotIn(self.u_admin.id_usuario, ids_contactos)
        self.assertNotIn(self.u_superadmin.id_usuario, ids_contactos)
