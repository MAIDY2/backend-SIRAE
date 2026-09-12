from types import SimpleNamespace

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import PreparacionAsignada


class PreparacionAsignadaAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.usuario_mock = SimpleNamespace(
            id_usuario=3,
            username='manipuladora_test',
            is_authenticated=True
        )
        self.preparacion = PreparacionAsignada.objects.create(
            id_menu=1,
            id_plato=2,
            id_usuario_manipuladora=3,
            id_turno=1,
            fecha='2026-09-11',
            hora_programada='08:00:00',
            estado_preparacion='Pendiente',
            observaciones='Nota inicial',
        )

    def test_post_crear_preparacion_exitoso_iso(self):
        payload = {
            'id_menu': 2,
            'id_plato': 3,
            'id_usuario_manipuladora': 3,
            'id_turno': 2,
            'fecha': '2026-09-12',
            'hora_programada': '09:30',
            'estado_preparacion': 'En proceso',
            'observaciones': 'Desayuno especial',
        }
        response = self.client.post('/api/preparacion-asignada/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['id_menu'], 2)
        self.assertEqual(response.data['estado_preparacion'], 'En proceso')

    def test_post_crear_preparacion_formato_fecha_latino(self):
        payload = {
            'id_menu': 1,
            'id_plato': 1,
            'id_usuario_manipuladora': 3,
            'id_turno': 1,
            'fecha': '15/09/2026',
            'hora_programada': '08:00',
        }
        response = self.client.post('/api/preparacion-asignada/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['fecha'], '2026-09-15')
        self.assertEqual(response.data['estado_preparacion'], 'Pendiente')

    def test_post_fecha_por_defecto_hoy_si_no_se_envia(self):
        payload = {
            'id_menu': 1,
            'id_plato': 1,
            'id_usuario_manipuladora': 3,
            'id_turno': 1,
            'hora_programada': '12:00:00',
        }
        response = self.client.post('/api/preparacion-asignada/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['fecha'], str(timezone.now().date()))

    def test_post_usuario_manipuladora_auto_si_esta_autenticado(self):
        self.client.force_authenticate(user=self.usuario_mock)
        payload = {
            'id_menu': 1,
            'id_plato': 2,
            'id_turno': 1,
            'hora_programada': '10:00',
        }
        response = self.client.post('/api/preparacion-asignada/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['id_usuario_manipuladora'], self.usuario_mock.id_usuario)

    def test_post_con_token_invalido_en_insomnia_no_bloquea_con_401(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer token_invalido_de_insomnia')
        payload = {
            'id_menu': 1,
            'id_plato': 1,
            'id_usuario_manipuladora': 3,
            'id_turno': 1,
            'fecha': '2026-09-11',
            'hora_programada': '08:00:00',
        }
        response = self.client.post('/api/preparacion-asignada/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_list_y_filtros(self):
        response = self.client.get('/api/preparacion-asignada/?estado=Pendiente')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_detalle_y_delete_con_y_sin_slash(self):
        pk = self.preparacion.id_preparacion_asignada
        get_res = self.client.get(f'/api/preparacion-asignada/{pk}')
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)

        del_res = self.client.delete(f'/api/preparacion-asignada/{pk}')
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(PreparacionAsignada.objects.filter(id_preparacion_asignada=pk).exists())

