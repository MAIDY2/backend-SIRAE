from datetime import date
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient

from apps_sirae.asistencia_diaria.models import AsistenciaDiaria
from apps_sirae.gramage.models import Gramage
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.unidades_medida.models import UnidadMedida
from .models import Grados, GrupoGramaje


def _fake_user(*, superadmin=False, supervisor=False):
    return type(
        'UsuarioPrueba',
        (),
        {
            'is_authenticated': True,
            'pk': 1 if superadmin else 2,
            'id_usuario': 1 if superadmin else 2,
            'es_super_administrador': lambda self: superadmin,
            'es_supervisor': lambda self: supervisor,
            'es_administrador': lambda self: False,
            'es_jefa_manipuladoras': lambda self: False,
        },
    )()


class GradosYGruposTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=_fake_user(superadmin=True))

        self.g_preescolar = GrupoGramaje.objects.create(
            nombre='Grupo A - Preescolar',
            nivel_educativo='PREESCOLAR',
            descripcion='Edades de 4 a 5 años',
        )
        self.g_primaria = GrupoGramaje.objects.create(
            nombre='Grupo B - Primaria',
            nivel_educativo='PRIMARIA',
            descripcion='Grados 1° a 5°',
        )
        self.g_secundaria = GrupoGramaje.objects.create(
            nombre='Grupo C - Secundaria',
            nivel_educativo='SECUNDARIA',
            descripcion='Grados 6° a 9°',
        )

    def test_crear_grado_asociado_a_grupo_e_identificar_grados_del_grupo(self):
        resp = self.client.post(
            '/api/grados/',
            {
                'nombre_grado': 'Transición',
                'id_grupo_gramaje': self.g_preescolar.id_grupo_gramaje,
                'nivel_educativo': 'PREESCOLAR',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['nombre_grupo_gramaje'], 'Grupo A - Preescolar')

        resp_grupo = self.client.get(f'/api/grupos-gramaje/{self.g_preescolar.id_grupo_gramaje}/')
        self.assertEqual(resp_grupo.status_code, 200)
        self.assertEqual(resp_grupo.data['grados_count'], 1)
        self.assertEqual(resp_grupo.data['grados_asociados'][0]['nombre_grado'], 'Transición')

    def test_rechaza_asociacion_con_nivel_incompatible_o_multiples_grupos(self):
        resp_incomp = self.client.post(
            '/api/grados/',
            {
                'nombre_grado': 'Jardín',
                'id_grupo_gramaje': self.g_secundaria.id_grupo_gramaje,
                'nivel_educativo': 'PREESCOLAR',
            },
            format='json',
        )
        self.assertEqual(resp_incomp.status_code, 400)
        self.assertIn('nivel_educativo', resp_incomp.data)

        resp_multi = self.client.post(
            '/api/grados/',
            {
                'nombre_grado': 'Primero',
                'id_grupo_gramaje': self.g_primaria.id_grupo_gramaje,
                'grupos_ids': [self.g_preescolar.id_grupo_gramaje, self.g_primaria.id_grupo_gramaje],
            },
            format='json',
        )
        self.assertEqual(resp_multi.status_code, 400)

    def test_reclasificacion_guarda_trazabilidad_y_calculos_usan_nueva_configuracion(self):
        grado = Grados.objects.create(
            nombre_grado='Quinto',
            id_grupo_gramaje=self.g_primaria,
            nivel_educativo='PRIMARIA',
        )
        gramo = UnidadMedida.objects.create(
            nombre='Gramo', abreviatura='g', tipo_magnitud='MASA', factor_conversion_base=Decimal('1')
        )
        arroz = Ingrediente.objects.create(nombre_ingrediente='Arroz', id_unidad_medida=gramo)
        Gramage.objects.create(
            id_ingrediente=arroz,
            id_grado=grado,
            id_unidad_medida=gramo,
            cantidad_gramaje=Decimal('150.000'),
        )

        # Reclasificar de Primaria a Secundaria
        resp_patch = self.client.patch(
            f'/api/grados/{grado.id_grado}/',
            {
                'id_grupo_gramaje': self.g_secundaria.id_grupo_gramaje,
                'nivel_educativo': 'SECUNDARIA',
                'motivo_cambio': 'Ajuste de resolución nutricional 2026',
            },
            format='json',
        )
        self.assertEqual(resp_patch.status_code, 200)

        # Historial debe conservar el periodo anterior (Primaria) y el nuevo (Secundaria)
        resp_hist = self.client.get(f'/api/grados/{grado.id_grado}/historial-clasificacion/')
        self.assertEqual(resp_hist.status_code, 200)
        self.assertEqual(len(resp_hist.data), 1)
        self.assertEqual(resp_hist.data[0]['nombre_grupo_anterior'], 'Grupo B - Primaria')
        self.assertEqual(resp_hist.data[0]['nombre_grupo_nuevo'], 'Grupo C - Secundaria')
        self.assertEqual(resp_hist.data[0]['nivel_anterior'], 'PRIMARIA')
        self.assertEqual(resp_hist.data[0]['nivel_nuevo'], 'SECUNDARIA')

        # Cálculo futuro por el grupo nuevo (Secundaria) incluye este grado; por el antiguo no
        calc_nuevo = self.client.get(
            f'/api/gramage/calcular-porciones/?id_grupo_gramaje={self.g_secundaria.id_grupo_gramaje}&estudiantes=10&dias=2'
        )
        self.assertEqual(calc_nuevo.status_code, 200)
        self.assertEqual(len(calc_nuevo.data['resultados']), 1)

        calc_antiguo = self.client.get(
            f'/api/gramage/calcular-porciones/?id_grupo_gramaje={self.g_primaria.id_grupo_gramaje}&estudiantes=10&dias=2'
        )
        self.assertEqual(calc_antiguo.status_code, 200)
        self.assertEqual(len(calc_antiguo.data['resultados']), 0)

    def test_no_permite_eliminar_grados_con_registros_historicos(self):
        grado_asist = Grados.objects.create(
            nombre_grado='Segundo',
            id_grupo_gramaje=self.g_primaria,
            nivel_educativo='PRIMARIA',
        )
        AsistenciaDiaria.objects.create(
            id_grado=grado_asist,
            fecha=date(2026, 5, 1),
            ninos_presentes=25,
        )
        resp_del = self.client.delete(f'/api/grados/{grado_asist.id_grado}/')
        self.assertEqual(resp_del.status_code, 400)

        # Grado sin historial ni relaciones sí se puede eliminar (ej. error de digitación)
        grado_nuevo = Grados.objects.create(
            nombre_grado='Borrador',
            id_grupo_gramaje=self.g_primaria,
            nivel_educativo='PRIMARIA',
        )
        resp_del_ok = self.client.delete(f'/api/grados/{grado_nuevo.id_grado}/')
        self.assertEqual(resp_del_ok.status_code, 204)

    def test_permisos_superadmin_en_grados_y_grupos(self):
        self.client.force_authenticate(user=_fake_user(supervisor=True))
        resp_get = self.client.get('/api/grupos-gramaje/')
        self.assertEqual(resp_get.status_code, 200)

        resp_post = self.client.post(
            '/api/grupos-gramaje/',
            {'nombre': 'Otro Grupo', 'nivel_educativo': 'MEDIA'},
            format='json',
        )
        self.assertEqual(resp_post.status_code, 403)
