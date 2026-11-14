from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps_sirae.jornadas.models import Jornada
from apps_sirae.secciones_menu.models import SeccionMenu


class SeccionMenuCrudTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.jornada_manana = Jornada.objects.create(nombre_jornada="Mañana")
        self.jornada_tarde = Jornada.objects.create(nombre_jornada="Tarde")
        self.seccion = SeccionMenu.objects.create(
            id_seccion=1,
            nombre_seccion="Desayuno",
            id_jornada=self.jornada_manana,
        )

    def test_list_secciones(self):
        response = self.client.get('/api/secciones_menu/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = [item['nombre_seccion'] for item in response.data.get('results', response.data)]
        self.assertIn("Desayuno", nombres)

    def test_create_seccion(self):
        payload = {
            "nombre_seccion": "Almuerzo",
            "id_jornada": self.jornada_manana.id_jornada,
        }
        response = self.client.post('/api/secciones_menu/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['nombre_seccion'], "Almuerzo")
        self.assertTrue(SeccionMenu.objects.filter(nombre_seccion="Almuerzo").exists())

    def test_update_seccion(self):
        payload = {
            "nombre_seccion": "Desayuno Actualizado",
            "id_jornada": self.jornada_tarde.id_jornada,
        }
        response = self.client.put(f'/api/secciones_menu/{self.seccion.id_seccion}/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.seccion.refresh_from_db()
        self.assertEqual(self.seccion.nombre_seccion, "Desayuno Actualizado")

    def test_delete_seccion(self):
        sec = SeccionMenu.objects.create(nombre_seccion="Temporal", id_jornada=self.jornada_manana)
        response = self.client.delete(f'/api/secciones_menu/{sec.id_seccion}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SeccionMenu.objects.filter(pk=sec.id_seccion).exists())
