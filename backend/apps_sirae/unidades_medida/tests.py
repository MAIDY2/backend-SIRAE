from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient

from apps_sirae.facturas_compra.models import InventarioCentral
from apps_sirae.grados.models import Grados, GrupoGramaje
from apps_sirae.gramage.models import Gramage
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.instituciones.models import Institucion
from apps_sirae.jornadas.models import Jornada
from apps_sirae.sede_jornada.models import SedeJornada
from apps_sirae.sedes.models import Sede
from .models import EquivalenciaUnidad, UnidadMedida
from .services import (
    ErrorConversionUnidad,
    convertir_cantidad,
    formatear_cantidad_apropiada,
)


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


class UnidadesMedidaConversionTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=_fake_user(superadmin=True))

        self.g = UnidadMedida.objects.create(
            nombre='Gramo', abreviatura='g', tipo_magnitud='MASA', factor_conversion_base=Decimal('1')
        )
        self.kg = UnidadMedida.objects.create(
            nombre='Kilogramo', abreviatura='kg', tipo_magnitud='MASA', factor_conversion_base=Decimal('1000')
        )
        self.ml = UnidadMedida.objects.create(
            nombre='Mililitro', abreviatura='ml', tipo_magnitud='VOLUMEN', factor_conversion_base=Decimal('1')
        )
        self.litro = UnidadMedida.objects.create(
            nombre='Litro', abreviatura='L', tipo_magnitud='VOLUMEN', factor_conversion_base=Decimal('1000')
        )
        self.und = UnidadMedida.objects.create(
            nombre='Unidad', abreviatura='und', tipo_magnitud='UNIDAD', factor_conversion_base=Decimal('1')
        )
        self.huevo = Ingrediente.objects.create(
            nombre_ingrediente='Huevo AA',
            id_unidad_medida=self.g,
        )
        self.leche = Ingrediente.objects.create(
            nombre_ingrediente='Leche Entera',
            id_unidad_medida=self.litro,
        )

    def test_auto_conversion_misma_magnitud(self):
        res_kg = convertir_cantidad(Decimal('250'), self.g, self.kg)
        self.assertEqual(res_kg, Decimal('0.250000'))

        res_ml = convertir_cantidad(Decimal('1.5'), self.litro, self.ml)
        self.assertEqual(res_ml, Decimal('1500.000000'))

    def test_rechaza_conversion_masa_a_volumen_sin_equivalencia(self):
        with self.assertRaises(ErrorConversionUnidad):
            convertir_cantidad(Decimal('100'), self.g, self.ml, ingrediente=self.leche)

        resp = self.client.post(
            '/api/unidades_medida/convertir/',
            {
                'cantidad': 100,
                'id_unidad_origen': self.g.id_unidad_medida,
                'id_unidad_destino': self.ml.id_unidad_medida,
                'id_ingrediente': self.leche.id_ingrediente,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['codigo'], 'CONVERSION_INVALIDA')

    def test_equivalencia_tecnica_permite_conversion_entre_magnitudes(self):
        # 1 und de Huevo AA = 55 g
        resp_eq = self.client.post(
            '/api/equivalencias-unidad/',
            {
                'id_ingrediente': self.huevo.id_ingrediente,
                'id_unidad_origen': self.und.id_unidad_medida,
                'id_unidad_destino': self.g.id_unidad_medida,
                'factor_conversion': '55.000000',
                'observaciones': 'Peso promedio huevo AA',
            },
            format='json',
        )
        self.assertEqual(resp_eq.status_code, 201)

        # Convertir 2 unidades de huevo a kilogramos vía 55 g / und
        resp_conv = self.client.post(
            '/api/unidades_medida/convertir/',
            {
                'cantidad': 2,
                'id_unidad_origen': self.und.id_unidad_medida,
                'id_unidad_destino': self.kg.id_unidad_medida,
                'id_ingrediente': self.huevo.id_ingrediente,
            },
            format='json',
        )
        self.assertEqual(resp_conv.status_code, 200)
        self.assertAlmostEqual(resp_conv.data['cantidad_convertida'], 0.11, places=4)

    def test_compatibles_identifica_magnitudes_y_equivalencias(self):
        EquivalenciaUnidad.objects.create(
            id_ingrediente=self.huevo,
            id_unidad_origen=self.und,
            id_unidad_destino=self.g,
            factor_conversion=Decimal('55'),
        )
        resp = self.client.get(
            f'/api/unidades_medida/compatibles/?id_ingrediente={self.huevo.id_ingrediente}'
        )
        self.assertEqual(resp.status_code, 200)
        por_id = {u['id_unidad_medida']: u for u in resp.data['unidades']}
        self.assertTrue(por_id[self.g.id_unidad_medida]['es_compatible'])
        self.assertTrue(por_id[self.kg.id_unidad_medida]['es_compatible'])
        self.assertTrue(por_id[self.und.id_unidad_medida]['es_compatible'])
        self.assertFalse(por_id[self.ml.id_unidad_medida]['es_compatible'])
        self.assertTrue(por_id[self.ml.id_unidad_medida]['requiere_equivalencia'])

    def test_presentacion_apropiada(self):
        pres_kg = formatear_cantidad_apropiada(Decimal('1500'), self.g)
        self.assertEqual(pres_kg['unidad'], 'kg')
        self.assertEqual(pres_kg['cantidad'], 1.5)

        pres_g = formatear_cantidad_apropiada(Decimal('0.05'), self.kg)
        self.assertEqual(pres_g['unidad'], 'g')
        self.assertEqual(pres_g['cantidad'], 50.0)

        pres_l = formatear_cantidad_apropiada(Decimal('2500'), self.ml)
        self.assertEqual(pres_l['unidad'], 'L')
        self.assertEqual(pres_l['cantidad'], 2.5)

    def test_calcular_mercado_convierte_unidades_y_alerta_conversion_invalida(self):
        grupo = GrupoGramaje.objects.create(nombre='Primaria', nivel_educativo='PRIMARIA')
        grado = Grados.objects.create(nombre_grado='Primero', id_grupo_gramaje=grupo, nivel_educativo='PRIMARIA')
        inst = Institucion.objects.create(nombre_institucion='IE Demo')
        sede = Sede.objects.create(id_institucion=inst, nombre_sede='Sede A')
        jornada = Jornada.objects.create(nombre_jornada='Mañana')
        SedeJornada.objects.create(id_sede=sede, id_jornada=jornada, cupos=100)

        arroz = Ingrediente.objects.create(nombre_ingrediente='Arroz', id_unidad_medida=self.kg)
        # Gramaje configurado en GRAMOS (120 g/estudiante) mientras inventario central es KILOGRAMOS
        Gramage.objects.create(
            id_ingrediente=arroz,
            id_grado=grado,
            id_unidad_medida=self.g,
            cantidad_gramaje=Decimal('120.000'),
        )
        # Producto con unidad incompatible sin equivalencia (ej. Leche en Litros pero gramaje creado en gramos directo vía ORM)
        Gramage.objects.create(
            id_ingrediente=self.leche,
            id_grado=grado,
            id_unidad_medida=self.g,
            cantidad_gramaje=Decimal('200.000'),
        )
        InventarioCentral.objects.create(id_ingrediente=arroz, cantidad_disponible=Decimal('500'))

        self.client.force_authenticate(user=_fake_user(supervisor=True))
        resp = self.client.get(f'/api/entregas/calcular-mercado/?id_sede={sede.id_sede}&dias=10')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['alertas_conversion']), 1)

        prods = {p['id_ingrediente']: p for p in resp.data['productos_sugeridos']}
        # 100 estudiantes * 0.120 kg * 10 dias = 120 kg
        self.assertEqual(prods[arroz.id_ingrediente]['consumo_teorico_periodo'], 120.0)
        self.assertFalse(prods[arroz.id_ingrediente]['error_conversion'])
        # Leche sin equivalencia g <-> L debe bloquear cálculo errado y emitir alerta
        self.assertTrue(prods[self.leche.id_ingrediente]['error_conversion'])
        self.assertEqual(prods[self.leche.id_ingrediente]['estado_bodega_central'], 'ERROR_CONVERSION')
        self.assertEqual(prods[self.leche.id_ingrediente]['cantidad_sugerida_despacho'], 0.0)

    def test_solo_superadmin_crea_unidades_y_supervisor_solo_consulta(self):
        self.client.force_authenticate(user=_fake_user(supervisor=True))
        resp_get = self.client.get('/api/unidades_medida/')
        self.assertEqual(resp_get.status_code, 200)

        resp_post = self.client.post(
            '/api/unidades_medida/',
            {'nombre': 'Onza', 'abreviatura': 'oz', 'tipo_magnitud': 'MASA', 'factor_conversion_base': '28.35'},
            format='json',
        )
        self.assertEqual(resp_post.status_code, 403)
