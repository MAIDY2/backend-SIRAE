from decimal import Decimal
from django.test import TestCase
from apps_sirae.inventario.models import Inventario
from apps_sirae.entregas.models import Entrega
from apps_sirae.instituciones.models import Institucion
from apps_sirae.sedes.models import Sede
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.tipos_mercado.models import TipoMercado


class InventarioAcumulacionTestCase(TestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(
            nombre_institucion="Colegio Test",
            codigo_dane="123456"
        )
        self.sede = Sede.objects.create(
            nombre_sede="Sede Principal",
            id_institucion=self.institucion
        )
        self.tipo_mercado = TipoMercado.objects.create(
            nombre_tipo="No Perecedero"
        )
        self.ingrediente = Ingrediente.objects.create(
            nombre_ingrediente="Arroz",
            marca_ingrediente="SIRAE"
        )

    def test_entregas_multiples_se_acumulan_en_un_solo_inventario(self):
        # Primera entrega de 5.00
        Entrega.objects.create(
            id_institucion=self.institucion,
            id_sede=self.sede,
            id_ingrediente=self.ingrediente.id_ingrediente,
            id_usuario_supervisor=1,
            id_tipo_mercado=self.tipo_mercado.id_tipo_mercado,
            fecha_entrega="2026-11-01",
            fecha_vencimiento="2026-12-01",
            cantidad=Decimal("5.00"),
            estado="EN_TRANSITO"
        )

        # Debe existir 1 solo registro de inventario con cantidad 5.00
        inventarios = Inventario.objects.filter(
            id_ingrediente=self.ingrediente.id_ingrediente,
            id_sede=self.sede
        )
        self.assertEqual(inventarios.count(), 1)
        self.assertEqual(inventarios.first().cantidad_actual, Decimal("5.00"))

        # Segunda entrega de 5.00 del mismo ingrediente para la misma sede
        Entrega.objects.create(
            id_institucion=self.institucion,
            id_sede=self.sede,
            id_ingrediente=self.ingrediente.id_ingrediente,
            id_usuario_supervisor=1,
            id_tipo_mercado=self.tipo_mercado.id_tipo_mercado,
            fecha_entrega="2026-11-02",
            fecha_vencimiento="2026-12-02",
            cantidad=Decimal("5.00"),
            estado="EN_TRANSITO"
        )

        # Debe seguir existiendo 1 solo registro pero acumulado en 10.00
        inventarios_actualizados = Inventario.objects.filter(
            id_ingrediente=self.ingrediente.id_ingrediente,
            id_sede=self.sede
        )
        self.assertEqual(inventarios_actualizados.count(), 1)
        self.assertEqual(inventarios_actualizados.first().cantidad_actual, Decimal("10.00"))

    def test_consolidacion_duplicados_existentes(self):
        # Simular duplicados históricos creados previamente de forma separada
        Inventario.objects.create(
            id_ingrediente=self.ingrediente.id_ingrediente,
            id_sede=self.sede,
            cantidad_actual=Decimal("5.00"),
            stock_minimo=Decimal("0.00"),
            id_unidad_medida=1
        )
        Inventario.objects.create(
            id_ingrediente=self.ingrediente.id_ingrediente,
            id_sede=self.sede,
            cantidad_actual=Decimal("5.00"),
            stock_minimo=Decimal("0.00"),
            id_unidad_medida=1
        )
        self.assertEqual(
            Inventario.objects.filter(id_ingrediente=self.ingrediente.id_ingrediente, id_sede=self.sede).count(),
            2
        )

        # Nueva entrega debe consolidar los duplicados anteriores y sumar la nueva cantidad (5 + 5 + 5 = 15)
        Entrega.objects.create(
            id_institucion=self.institucion,
            id_sede=self.sede,
            id_ingrediente=self.ingrediente.id_ingrediente,
            id_usuario_supervisor=1,
            id_tipo_mercado=self.tipo_mercado.id_tipo_mercado,
            fecha_entrega="2026-11-03",
            fecha_vencimiento="2026-12-03",
            cantidad=Decimal("5.00"),
            estado="EN_TRANSITO"
        )

        registros = Inventario.objects.filter(
            id_ingrediente=self.ingrediente.id_ingrediente,
            id_sede=self.sede
        )
        self.assertEqual(registros.count(), 1)
        self.assertEqual(registros.first().cantidad_actual, Decimal("15.00"))
