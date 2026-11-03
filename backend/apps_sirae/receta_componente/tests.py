from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework import serializers
from rest_framework.test import APIRequestFactory, force_authenticate

from apps_sirae.ia_sugerencias.views import (
    construir_ingredientes_sugeridos,
    sugerencias_recetas_ia,
)
from apps_sirae.receta_componente.api.serializer import RecetaComponenteSerializer


class RecetaComponenteSerializerTests(SimpleTestCase):
    def test_total_preparation_requires_a_positive_portion_base(self):
        serializer = RecetaComponenteSerializer()

        with self.assertRaises(serializers.ValidationError):
            serializer.validate({
                'cantidad': Decimal('12'),
                'base_cantidad': 'TOTAL_PREPARACION',
                'porciones_base': None,
            })

    def test_per_child_quantity_clears_the_total_portion_base(self):
        serializer = RecetaComponenteSerializer()

        validated = serializer.validate({
            'cantidad': Decimal('0.25'),
            'base_cantidad': 'POR_NINO',
            'porciones_base': 12,
        })

        self.assertIsNone(validated['porciones_base'])

    def test_quantity_must_be_positive(self):
        serializer = RecetaComponenteSerializer()

        with self.assertRaises(serializers.ValidationError):
            serializer.validate({
                'cantidad': Decimal('0'),
                'base_cantidad': 'POR_NINO',
                'porciones_base': None,
            })


class RecipeSuggestionCalculationTests(SimpleTestCase):
    def test_returns_per_child_and_total_for_both_quantity_bases(self):
        ingrediente_por_nino = SimpleNamespace(
            id_ingrediente=1,
            nombre_ingrediente='Arroz',
            id_unidad_medida_id=4,
        )
        ingrediente_total = SimpleNamespace(
            id_ingrediente=2,
            nombre_ingrediente='Frijol',
            id_unidad_medida_id=4,
        )
        componentes = [
            SimpleNamespace(
                id_ingrediente=ingrediente_por_nino,
                cantidad=Decimal('0.25'),
                base_cantidad='POR_NINO',
                porciones_base=None,
            ),
            SimpleNamespace(
                id_ingrediente=ingrediente_total,
                cantidad=Decimal('3'),
                base_cantidad='TOTAL_PREPARACION',
                porciones_base=6,
            ),
        ]
        inventario = [
            SimpleNamespace(
                id_ingrediente=1,
                id_unidad_medida=4,
                cantidad_actual=Decimal('5'),
            ),
            SimpleNamespace(
                id_ingrediente=2,
                id_unidad_medida=4,
                cantidad_actual=Decimal('6'),
            ),
        ]

        sugeridos = construir_ingredientes_sugeridos(
            componentes,
            inventario,
            {4: 'kg'},
            12,
        )

        self.assertEqual(sugeridos[0]['cantidad_por_nino'], '0.25')
        self.assertEqual(sugeridos[0]['cantidad_total'], '3.00')
        self.assertTrue(sugeridos[0]['alcanza'])
        self.assertEqual(sugeridos[1]['cantidad_por_nino'], '0.5')
        self.assertEqual(sugeridos[1]['cantidad_total'], '6.0')
        self.assertTrue(sugeridos[1]['alcanza'])

    def test_does_not_compare_inventory_with_different_units(self):
        ingrediente = SimpleNamespace(
            id_ingrediente=1,
            nombre_ingrediente='Arroz',
            id_unidad_medida_id=4,
        )
        componente = SimpleNamespace(
            id_ingrediente=ingrediente,
            cantidad=Decimal('0.25'),
            base_cantidad='POR_NINO',
            porciones_base=None,
        )
        inventario = [
            SimpleNamespace(
                id_ingrediente=1,
                id_unidad_medida=8,
                cantidad_actual=Decimal('100'),
            ),
        ]

        sugerido = construir_ingredientes_sugeridos(
            [componente],
            inventario,
            {4: 'kg'},
            12,
        )[0]

        self.assertFalse(sugerido['unidad_compatible'])
        self.assertIsNone(sugerido['cantidad_disponible'])
        self.assertFalse(sugerido['alcanza'])


class RecipeSuggestionEndpointTests(SimpleTestCase):
    def test_endpoint_returns_preview_and_does_not_change_recipe(self):
        usuario = SimpleNamespace(
            id_sede_id=5,
            is_authenticated=True,
            es_jefa_manipuladoras=lambda: True,
            es_manipuladora=lambda: False,
        )
        plato = SimpleNamespace(nombre_plato='Sopa')
        ingrediente = SimpleNamespace(
            id_ingrediente=8,
            nombre_ingrediente='Arroz',
            id_unidad_medida_id=4,
        )
        componente = SimpleNamespace(
            id_ingrediente=ingrediente,
            id_ingrediente_id=8,
            id_plato=plato,
            cantidad=Decimal('0.25'),
            base_cantidad='POR_NINO',
            porciones_base=None,
        )
        inventario_item = SimpleNamespace(
            id_ingrediente=8,
            id_unidad_medida=4,
            cantidad_actual=Decimal('4'),
        )
        receta_query = Mock()
        receta_query.select_related.return_value.order_by.return_value = [componente]
        unidad_query = Mock()
        unidad_query.values_list.return_value = [(4, 'kg')]
        request = APIRequestFactory().post(
            '/api/ia/sugerencias-recetas/',
            {'id_menu': 9, 'id_plato': 3},
            format='json',
        )
        force_authenticate(request, user=usuario)

        with (
            patch(
                'apps_sirae.ia_sugerencias.views.Menu.objects.get',
                return_value=SimpleNamespace(id_menu=9, ninos_presentes=12),
            ),
            patch(
                'apps_sirae.ia_sugerencias.views.DetallePlato.objects.filter',
                return_value=SimpleNamespace(exists=lambda: True),
            ),
            patch(
                'apps_sirae.ia_sugerencias.views.RecetaComponente.objects.filter',
                return_value=receta_query,
            ),
            patch(
                'apps_sirae.ia_sugerencias.views.Inventario.objects.filter',
                return_value=[inventario_item],
            ),
            patch(
                'apps_sirae.ia_sugerencias.views.UnidadMedida.objects.filter',
                return_value=unidad_query,
            ),
        ):
            response = sugerencias_recetas_ia(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['ingredientes'][0]['cantidad_por_nino'], '0.25')
        self.assertEqual(response.data['ingredientes'][0]['cantidad_total'], '3.00')
        self.assertTrue(response.data['ingredientes'][0]['alcanza'])
        self.assertEqual(componente.cantidad, Decimal('0.25'))

    def test_endpoint_rejects_non_manipulator_roles(self):
        usuario = SimpleNamespace(
            is_authenticated=True,
            es_jefa_manipuladoras=lambda: False,
            es_manipuladora=lambda: False,
        )
        request = APIRequestFactory().post(
            '/api/ia/sugerencias-recetas/',
            {'id_menu': 9, 'id_plato': 3},
            format='json',
        )
        force_authenticate(request, user=usuario)

        response = sugerencias_recetas_ia(request)

        self.assertEqual(response.status_code, 403)

# Create your tests here.
