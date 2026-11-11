
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.secciones_menu.models import SeccionMenu
from apps_sirae.platos.models import Plato
from apps_sirae.detalle_plato.models import DetallePlato


class EndpointsSiraeTestCase(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.client.force_authenticate(user=type(
            'Administrador',
            (),
            {
                'is_authenticated': True,
                'es_jefa_manipuladoras': lambda self: False,
                'es_administrador': lambda self: True,
                'es_super_administrador': lambda self: False,
            },
        )())

        # Datos iniciales para pruebas
        self.seccion = SeccionMenu.objects.create(
            nombre_seccion="Desayuno",
            id_jornada=1
        )

        self.plato = Plato.objects.create(
            nombre_plato="Avena con Frutas",
            componente="Cereal y fruta",
            id_seccion=self.seccion
        )

        self.unidad = UnidadMedida.objects.create(
            nombre="Gramos",
            abreviatura="g"
        )

        self.detalle = DetallePlato.objects.create(
            id_menu=10,
            id_plato=self.plato,
            porcion_por_nino=50.0,
            total_a_preparar=5000.0,
            unidad_total="g",
            estado_preparacion="Pendiente"
        )

    # 1. Unidades de medida: crear, consultar y actualizar
    def test_unidades_medida_crud_sin_entradas_asociadas(self):

        # Esta operación requiere Super Administrador
        super_admin = type(
            'SuperAdministrador',
            (),
            {
                'is_authenticated': True,
                'es_super_administrador': lambda self: True,
                'es_administrador': lambda self: False,
                'es_jefa_manipuladoras': lambda self: False,
            },
        )()

        self.client.force_authenticate(user=super_admin)

        res_list = self.client.get('/api/unidades_medida/')

        self.assertEqual(
            res_list.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(len(res_list.data), 1)

        res_create = self.client.post(
            '/api/unidades_medida/',
            {
                'nombre': 'Kilogramos',
                'abreviatura': 'kg'
            },
            format='json'
        )

        self.assertEqual(
            res_create.status_code,
            status.HTTP_201_CREATED,
            res_create.data
        )

        nuevo_id = res_create.data['id_unidad_medida']

        res_retrieve = self.client.get(
            f'/api/unidades_medida/{nuevo_id}/'
        )

        self.assertEqual(
            res_retrieve.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            res_retrieve.data['nombre'],
            'Kilogramos'
        )

        res_update = self.client.put(
            f'/api/unidades_medida/{nuevo_id}/',
            {
                'nombre': 'Kilos',
                'abreviatura': 'kg'
            },
            format='json'
        )

        self.assertEqual(
            res_update.status_code,
            status.HTTP_200_OK,
            res_update.data
        )

        self.assertEqual(
            res_update.data['nombre'],
            'Kilos'
        )

    # 2. Secciones de menú: solo listar y consultar detalle
    def test_secciones_menu_solo_listar(self):

        res_list = self.client.get('/api/secciones_menu/')

        self.assertEqual(
            res_list.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(len(res_list.data), 1)

        res_detail = self.client.get(
            f'/api/secciones_menu/{self.seccion.id_seccion}/'
        )

        self.assertEqual(
            res_detail.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            res_detail.data['nombre_seccion'],
            'Desayuno'
        )

        res_post = self.client.post(
            '/api/secciones_menu/',
            {'nombre_seccion': 'Almuerzo'}
        )

        self.assertEqual(
            res_post.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED
        )

        res_del = self.client.delete(
            f'/api/secciones_menu/{self.seccion.id_seccion}/'
        )

        self.assertEqual(
            res_del.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED
        )

    # 3. Platos: lectura y escritura
    def test_platos_solo_listar(self):

        res_list = self.client.get('/api/platos/')

        self.assertEqual(
            res_list.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(len(res_list.data), 1)

        res_detail = self.client.get(
            f'/api/platos/{self.plato.id_plato}/'
        )

        self.assertEqual(
            res_detail.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            res_detail.data['nombre_plato'],
            'Avena con Frutas'
        )

        res_post = self.client.post(
            '/api/platos/',
            {'nombre_plato': 'Sopa'}
        )

        self.assertEqual(
            res_post.status_code,
            status.HTTP_201_CREATED
        )

        res_del = self.client.delete(
            f"/api/platos/{res_post.data['id_plato']}/"
        )

        self.assertEqual(
            res_del.status_code,
            status.HTTP_204_NO_CONTENT
        )

    # 4. Detalle de plato: lectura y escritura
    def test_detalle_plato_solo_listar(self):

        res_list = self.client.get('/api/detalle_plato/')

        self.assertEqual(
            res_list.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(len(res_list.data), 1)

        res_detail = self.client.get(
            f'/api/detalle_plato/{self.detalle.id_detalle_plato}/'
        )

        self.assertEqual(
            res_detail.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            res_detail.data['estado_preparacion'],
            'Pendiente'
        )

        res_post = self.client.post(
            '/api/detalle_plato/',
            {'estado_preparacion': 'Listo'}
        )

        self.assertEqual(
            res_post.status_code,
            status.HTTP_201_CREATED
        )

        res_del = self.client.delete(
            f"/api/detalle_plato/{res_post.data['id_detalle_plato']}/"
        )

        self.assertEqual(
            res_del.status_code,
            status.HTTP_204_NO_CONTENT
        )

    # 5. El supervisor no puede consultar ni modificar menús y platos
    def test_supervisor_cannot_read_or_change_menus_and_dishes(self):

        supervisor = type(
            'Supervisor',
            (),
            {
                'is_authenticated': True,
                'es_jefa_manipuladoras': lambda self: False,
                'es_administrador': lambda self: False,
                'es_super_administrador': lambda self: False,
                'es_supervisor': lambda self: True,
            },
        )()

        self.client.force_authenticate(user=supervisor)

        self.assertEqual(
            self.client.get('/api/platos/').status_code,
            status.HTTP_403_FORBIDDEN
        )

        self.assertEqual(
            self.client.get('/api/detalle_plato/').status_code,
            status.HTTP_403_FORBIDDEN
        )
