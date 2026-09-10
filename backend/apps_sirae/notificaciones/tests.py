from datetime import datetime, timezone
from types import SimpleNamespace

from rest_framework.test import APITestCase

from .models import Notificacion


class NotificacionApiTestCase(APITestCase):
    def setUp(self):
        self.usuario = SimpleNamespace(
            id_usuario=10,
            is_authenticated=True,
            es_administrador=lambda: False,
        )
        self.otro_usuario = SimpleNamespace(
            id_usuario=20,
            is_authenticated=True,
            es_administrador=lambda: False,
        )
        self.notificacion = Notificacion.objects.create(
            id_usuario=10,
            titulo='Aviso de prueba',
            mensaje='Mensaje de prueba',
            fecha_hora=datetime.now(timezone.utc),
        )
        Notificacion.objects.create(
            id_usuario=20,
            titulo='Aviso privado',
            mensaje='No debe aparecer para el usuario 10',
            fecha_hora=datetime.now(timezone.utc),
        )

    def request(self, method, path, user=None, data=None):
        self.client.force_authenticate(user=user or self.usuario)
        return getattr(self.client, method)(path, data=data, format='json')

    def test_lista_solo_notificaciones_del_usuario(self):
        response = self.request('get', '/api/notificaciones/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id_usuario'], 10)

    def test_consulta_no_leidas_devuelve_cantidad_y_resultados(self):
        response = self.request('get', '/api/notificaciones/no-leidas/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['cantidad'], 1)
        self.assertEqual(len(response.data['resultados']), 1)

    def test_marcar_notificacion_como_leida(self):
        response = self.request(
            'post',
            f'/api/notificaciones/{self.notificacion.id_notificacion}/marcar-leida/',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['leida'])
        self.notificacion.refresh_from_db()
        self.assertTrue(self.notificacion.leida)

    def test_crear_notificacion_sin_fecha_usa_la_fecha_actual(self):
        response = self.request(
            'post',
            '/api/notificaciones/',
            data={
                'titulo': 'Nueva notificación',
                'mensaje': 'Creada desde el frontend',
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['id_usuario'], 10)
        self.assertFalse(response.data['leida'])
        self.assertIsNotNone(response.data['fecha_hora'])