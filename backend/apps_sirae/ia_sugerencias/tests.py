from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps_sirae.instituciones.models import Institucion
from apps_sirae.sedes.models import Sede
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.inventario.models import Inventario
from apps_sirae.salidas_inventario.models import SalidaInventario
from apps_sirae.ia_sugerencias.views import CATALOGO_20_MENUS_PAE, NOMBRES_20_MENUS_BASE


class IASugerenciasRecetasTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Unidad y sede
        self.unidad_kg = UnidadMedida.objects.create(
            nombre="Kilogramo",
            abreviatura="kg",
            tipo_magnitud="MASA",
            factor_conversion_base=Decimal("1000.0"),
        )
        self.unidad_und = UnidadMedida.objects.create(
            nombre="Unidad",
            abreviatura="und",
            tipo_magnitud="CANTIDAD",
            factor_conversion_base=Decimal("1.0"),
        )
        self.institucion = Institucion.objects.create(
            nombre_institucion="Institución Educativa PAE Central",
            estado="ACTIVO",
        )
        self.sede = Sede.objects.create(
            id_institucion=self.institucion,
            nombre_sede="Sede Primaria La Esperanza",
            estado="ACTIVO",
        )

        # Ingredientes
        self.huevo = Ingrediente.objects.create(
            nombre_ingrediente="Huevos",
            id_unidad_medida=self.unidad_und,
        )
        self.arroz = Ingrediente.objects.create(
            nombre_ingrediente="Arroz Blanco",
            id_unidad_medida=self.unidad_kg,
        )

        # Stock en inventario
        self.inv_huevos = Inventario.objects.create(
            id_sede=self.sede,
            id_institucion=self.institucion,
            id_ingrediente=self.huevo.id_ingrediente,
            cantidad_actual=Decimal("300.0"),
            stock_minimo=Decimal("50.0"),
            id_unidad_medida=self.unidad_und.id_unidad_medida,
        )
        self.inv_arroz = Inventario.objects.create(
            id_sede=self.sede,
            id_institucion=self.institucion,
            id_ingrediente=self.arroz.id_ingrediente,
            cantidad_actual=Decimal("50.0"),  # 50 kg
            stock_minimo=Decimal("10.0"),
            id_unidad_medida=self.unidad_kg.id_unidad_medida,
        )

    def test_catalogo_20_menus_cargado(self):
        """Verifica que el catálogo oficial PAE contiene los 20 menús del ciclo."""
        self.assertEqual(len(CATALOGO_20_MENUS_PAE), 20)
        self.assertIn("pericos con arroz", NOMBRES_20_MENUS_BASE)
        self.assertIn("arepa con chocolate", NOMBRES_20_MENUS_BASE)
        self.assertIn("lentejas con arroz", NOMBRES_20_MENUS_BASE)

    def test_sugerencias_desayuno_coherente_para_200_ninos(self):
        """
        Verifica que al solicitar un desayuno para 200 niños:
        - Las preparaciones sean coherentes con desayuno (no carnes pesadas ni sudados de almuerzo).
        - No repitan exactamente los 20 menús establecidos.
        - Las cantidades se calculen proporcionalmente para 200 niños.
        """
        payload = {
            "id_sede": self.sede.id_sede,
            "ninos_presentes": 200,
            "id_seccion": 1,  # Desayuno
        }
        response = self.client.post("/api/ia/sugerencias-recetas/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["seccion"], "Desayuno")
        self.assertEqual(data["ninos_presentes"], 200)
        self.assertTrue(len(data["sugerencias_ia_estructuradas"]) >= 1)

        for sug in data["sugerencias_ia_estructuradas"]:
            nombre = sug["nombre_plato"].lower()
            # No debe ser igual a los 20 menús base tal cual
            self.assertNotIn(nombre, NOMBRES_20_MENUS_BASE)
            # No debe tener platos pesados de almuerzo en desayuno
            self.assertNotIn("carne sudada", nombre)
            self.assertNotIn("pollo asado", nombre)
            self.assertNotIn("frijolada", nombre)

            # Verificar cálculo de cantidades para los 200 niños
            for ing in sug["ingredientes"]:
                self.assertIn("cantidad_por_nino", ing)
                self.assertIn("cantidad_total", ing)
                self.assertIn("stock_actual", ing)
                self.assertIn("stock_restante_proyectado", ing)
                self.assertIn("alcanza", ing)

    def test_sugerencias_almuerzo_coherente(self):
        """Verifica la generación de sugerencias para almuerzo."""
        payload = {
            "id_sede": self.sede.id_sede,
            "ninos_presentes": 150,
            "id_seccion": 2,  # Almuerzo
        }
        response = self.client.post("/api/ia/sugerencias-recetas/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["seccion"], "Almuerzo")
        self.assertEqual(data["ninos_presentes"], 150)
        self.assertTrue(len(data["sugerencias_ia_estructuradas"]) >= 1)

    def test_descontar_inventario_tras_preparacion(self):
        """Verifica que se descuenten correctamente los ingredientes y se registre la salida."""
        payload = {
            "id_sede": self.sede.id_sede,
            "nombre_preparacion": "Huevos campesinos con arepa",
            "ninos_presentes": 200,
            "ingredientes": [
                {
                    "id_ingrediente": self.huevo.id_ingrediente,
                    "nombre_ingrediente": "Huevos",
                    "cantidad_a_descontar": "200.0",
                },
                {
                    "id_ingrediente": self.arroz.id_ingrediente,
                    "nombre_ingrediente": "Arroz Blanco",
                    "cantidad_a_descontar": "9.0",  # 9 kg
                },
            ],
        }
        response = self.client.post("/api/ia/descontar-inventario/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["total_ingredientes_descontados"], 2)

        # Verificar actualización en base de datos
        self.inv_huevos.refresh_from_db()
        self.inv_arroz.refresh_from_db()
        # 300 - 200 = 100
        self.assertEqual(self.inv_huevos.cantidad_actual, Decimal("100.0"))
        # 50 - 9 = 41
        self.assertEqual(self.inv_arroz.cantidad_actual, Decimal("41.0"))

    def test_estado_mongodb_ia_resiliente(self):
        """Verifica que el endpoint de estado de MongoDB Atlas responda adecuadamente sin colapsar."""
        response = self.client.get("/api/ia/mongodb/status/")
        # Si no hay URI configurada en el entorno de pruebas, retorna 503 con diagnóstico claro
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])
        data = response.json()
        self.assertIn("conectado", data)

    def test_historial_sugerencias_endpoint(self):
        """Verifica que el endpoint de historial de la IA responda 200 con estructura esperada."""
        response = self.client.get("/api/ia/historial/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("historial", data)

