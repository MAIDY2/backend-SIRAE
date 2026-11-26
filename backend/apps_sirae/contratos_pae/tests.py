from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps_sirae.instituciones.models import Institucion
from apps_sirae.sedes.models import Sede
from .api.serializer import ContratoSerializer
from .models import Contrato, DistribucionSede


class ContratoUnicoPorInstitucionTests(TestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(
            nombre_institucion='I.E. Prueba Unica',
            nit='900111222-3',
        )
        self.contrato = Contrato.objects.create(
            numero_cor='COR-2026-100',
            institucion=self.inst.nombre_institucion,
            id_institucion=self.inst,
            estado='Activo',
            cupos=120,
        )

    def test_rechaza_segundo_contrato_misma_institucion_por_id(self):
        serializer = ContratoSerializer(data={
            'numero_cor': 'COR-2026-101',
            'institucion': self.inst.nombre_institucion,
            'id_institucion': self.inst.id_institucion,
            'estado': 'Activo',
            'cupos': 80,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('id_institucion', serializer.errors)

    def test_rechaza_segundo_contrato_misma_institucion_por_nombre(self):
        serializer = ContratoSerializer(data={
            'numero_cor': 'COR-2026-102',
            'institucion': 'i.e. prueba unica',
            'estado': 'Activo',
            'cupos': 50,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('id_institucion', serializer.errors)

    def test_permite_editar_mismo_contrato(self):
        serializer = ContratoSerializer(
            instance=self.contrato,
            data={'cupos': 200},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        actualizado = serializer.save()
        self.assertEqual(actualizado.cupos, 200)


class LimpiarContratosDuplicadosTests(TestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(
            nombre_institucion='I.E. Piagua Test',
            nit='900555666-1',
        )
        self.sede_a = Sede.objects.create(id_institucion=self.inst, nombre_sede='Sede Principal')
        self.sede_b = Sede.objects.create(id_institucion=self.inst, nombre_sede='Sede Rural')

        self.principal = Contrato.objects.create(
            numero_cor='COR-2026-001',
            institucion='I.E. Piagua Test',
            id_institucion=self.inst,
            estado='Activo',
            cupos=200,
        )
        self.duplicado = Contrato.objects.create(
            numero_cor='COR-2026-002',
            institucion='i.e. piagua test',
            estado='Activo',
            cupos=100,
        )
        DistribucionSede.objects.create(id_contrato=self.principal, id_sede=self.sede_a, cupos_asignados=120)
        DistribucionSede.objects.create(id_contrato=self.duplicado, id_sede=self.sede_b, cupos_asignados=80)

    def test_dry_run_no_elimina_contratos(self):
        out = StringIO()
        call_command('limpiar_contratos_duplicados', stdout=out)
        self.assertEqual(Contrato.objects.count(), 2)
        self.assertIn('MODO SIMULACIÓN', out.getvalue())

    def test_aplicar_consolida_sedes_y_elimina_duplicado(self):
        out = StringIO()
        call_command('limpiar_contratos_duplicados', '--aplicar', stdout=out)
        self.assertEqual(Contrato.objects.count(), 1)
        self.assertTrue(Contrato.objects.filter(pk=self.principal.pk).exists())
        self.assertEqual(
            DistribucionSede.objects.filter(id_contrato=self.principal).count(),
            2,
        )
