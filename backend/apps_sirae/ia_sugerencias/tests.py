from decimal import Decimal
import os
from unittest.mock import patch
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status

from apps_sirae.instituciones.models import Institucion
from apps_sirae.sedes.models import Sede
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.inventario.models import Inventario
from apps_sirae.salidas_inventario.models import SalidaInventario
from apps_sirae.ia_sugerencias.mongodb import get_mongo_uri, get_mongo_db_name
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

    def test_historial_sugerencias_limite_invalido(self):
        """Verifica que un parámetro limite inválido no genere error 500."""
        response = self.client.get("/api/ia/historial/?limite=no_numerico")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "success")

    @override_settings(MONGO_URI="", MONGO_DB_NAME="", MONGO_DISABLE_ENV_FALLBACK=False)
    def test_resolucion_variables_entorno_alternativas_mongo(self):
        """Verifica soporte de alias comunes en Render como MONGO_URL y MONGODB_DATABASE."""
        env_clean = {k: "" for k in ("MONGO_URI", "MONGODB_URI", "MONGO_URL", "MONGODB_URL", "MONGO_ATLAS_URI", "MONGODB_ATLAS_URI", "MONGO_CONNECTION_STRING", "MONGO_DB_NAME", "MONGODB_DB_NAME", "MONGO_DATABASE", "MONGODB_DATABASE")}
        env_clean["MONGO_URL"] = "mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority"
        env_clean["MONGODB_DATABASE"] = "sirae_ia_prod"
        with patch.dict(os.environ, env_clean, clear=False):
            self.assertEqual(get_mongo_uri(), env_clean["MONGO_URL"])
            self.assertEqual(get_mongo_db_name(), "sirae_ia_prod")

    def test_sugerencias_registra_motor_deterministico_en_mongo(self):
        """Verifica que al usar fallback determinístico se envíe motor_ia correcto a MongoDB."""
        with patch("apps_sirae.ia_sugerencias.views.generar_con_openai", return_value=None), \
             patch("apps_sirae.ia_sugerencias.views.sincronizar_catalogo_recetas", return_value=20) as mock_sync, \
             patch("apps_sirae.ia_sugerencias.views.guardar_historial_sugerencia", return_value="65f000000000000000000001") as mock_hist:
            payload = {
                "id_sede": self.sede.id_sede,
                "ninos_presentes": 120,
                "id_seccion": 1,
            }
            response = self.client.post("/api/ia/sugerencias-recetas/", payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()
            self.assertTrue(data["mongodb_atlas"]["activo"])
            self.assertEqual(data["mongodb_atlas"]["id_registro_historial"], "65f000000000000000000001")
            mock_sync.assert_called_once()
            mock_hist.assert_called_once()
            registro_guardado = mock_hist.call_args[0][0]
            self.assertEqual(registro_guardado["motor_ia"], "Motor PAE Colombiano")

    def test_sin_alimentos_suficientes_para_200_ninos_muestra_alertas_y_no_marca_viable(self):
        """Si el stock real no alcanza para 200 niños, debe marcar INSUFICIENTE y mostrar faltantes (no disponible)."""
        self.inv_huevos.cantidad_actual = Decimal("40.0")  # Solo alcanza para 40 niños
        self.inv_huevos.save(update_fields=["cantidad_actual"])
        self.inv_arroz.cantidad_actual = Decimal("2.0")    # 2 kg = 2000 g -> 44 niños
        self.inv_arroz.save(update_fields=["cantidad_actual"])

        with patch("apps_sirae.ia_sugerencias.views.generar_con_openai", return_value=None):
            payload = {
                "id_sede": self.sede.id_sede,
                "ninos_presentes": 200,
                "id_seccion": 1,
                "generar_imagen": False,
            }
            response = self.client.post("/api/ia/sugerencias-recetas/", payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()

            self.assertFalse(data["inventario_suficiente"])
            self.assertEqual(data["estado_inventario_general"], "INSUFICIENTE")
            self.assertEqual(data["ninos_maximos_atendibles"], 40)
            self.assertEqual(len(data["ingredientes_insuficientes"]), 2)
            self.assertIn("No hay alimentos suficientes", data["sugerencias"])
            # Debe devolver recetas de referencia colombianas marcadas como NO viables con ingredientes en False
            self.assertTrue(len(data["sugerencias_ia_estructuradas"]) >= 1)
            for sug in data["sugerencias_ia_estructuradas"]:
                self.assertFalse(sug["viable_con_inventario"])
                self.assertIn(sug["estado_inventario"], ["INSUFICIENTE", "AGOTADO"])
                self.assertTrue(any(not ing["alcanza"] for ing in sug["ingredientes"]))

    def test_muchos_estudiantes_con_un_solo_producto_sobrado_no_marca_todo_disponible(self):
        """Con 1000 estudiantes, aunque el arroz alcance, si faltan huevos NO debe marcar inventario suficiente."""
        self.inv_arroz.cantidad_actual = Decimal("100.0")  # 100 kg -> cubre ~2222 niños
        self.inv_arroz.save(update_fields=["cantidad_actual"])
        self.inv_huevos.cantidad_actual = Decimal("50.0")  # Solo 50 niños
        self.inv_huevos.save(update_fields=["cantidad_actual"])

        with patch("apps_sirae.ia_sugerencias.views.generar_con_openai", return_value=None):
            payload = {
                "id_sede": self.sede.id_sede,
                "estudiantes": 1000,
                "id_seccion": 1,
                "generar_imagen": False,
            }
            response = self.client.post("/api/ia/sugerencias-recetas/", payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()

            self.assertEqual(data["ninos_presentes"], 1000)
            self.assertFalse(data["inventario_suficiente"])
            self.assertEqual(data["estado_inventario_general"], "INSUFICIENTE")
            for sug in data["sugerencias_ia_estructuradas"]:
                self.assertFalse(sug["viable_con_inventario"])
                estados = {ing["estado_stock"] for ing in sug["ingredientes"]}
                self.assertTrue(bool(estados & {"INSUFICIENTE", "AGOTADO"}))

    def test_alerta_bajo_monto_cuando_stock_restante_queda_debajo_del_minimo(self):
        """Si alcanza para 260 niños pero quedan 40 huevos (stock_minimo=50), debe marcar BAJO_STOCK."""
        with patch("apps_sirae.ia_sugerencias.views.generar_con_openai", return_value=None):
            payload = {
                "id_sede": self.sede.id_sede,
                "ninos_presentes": 260,
                "id_seccion": 1,
                "generar_imagen": False,
            }
            response = self.client.post("/api/ia/sugerencias-recetas/", payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()

            self.assertTrue(data["inventario_suficiente"])
            self.assertEqual(data["estado_inventario_general"], "BAJO_STOCK")
            self.assertTrue(len(data["ingredientes_bajo_stock"]) >= 1)
            self.assertEqual(data["ingredientes_bajo_stock"][0]["estado_stock"], "BAJO_STOCK")
            sug = data["sugerencias_ia_estructuradas"][0]
            self.assertTrue(sug["tiene_stock_bajo"])
            self.assertEqual(sug["estado_inventario"], "BAJO_STOCK")
            huevos_ing = next(i for i in sug["ingredientes"] if "huevo" in i["nombre_ingrediente"].lower())
            self.assertTrue(huevos_ing["stock_bajo"])
            self.assertEqual(huevos_ing["estado_stock"], "BAJO_STOCK")
            self.assertEqual(huevos_ing["estado_stock_label"], "Bajo monto")

    def test_sede_con_inventario_vacio_y_stock_cero_reporta_agotado(self):
        """Si la sede no tiene existencias o tiene stock 0, debe reportar AGOTADO ('No hay')."""
        sede_vacia = Sede.objects.create(
            id_institucion=self.institucion,
            nombre_sede="Sede Sin Stock",
            estado="ACTIVO",
        )
        Inventario.objects.create(
            id_sede=sede_vacia,
            id_institucion=self.institucion,
            id_ingrediente=self.huevo.id_ingrediente,
            cantidad_actual=Decimal("0.00"),
            stock_minimo=Decimal("20.00"),
            id_unidad_medida=self.unidad_und.id_unidad_medida,
        )
        with patch("apps_sirae.ia_sugerencias.views.generar_con_openai", return_value=None):
            payload = {
                "id_sede": sede_vacia.id_sede,
                "ninos_presentes": 200,
                "id_seccion": 1,
                "generar_imagen": False,
            }
            response = self.client.post("/api/ia/sugerencias-recetas/", payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()

            self.assertFalse(data["inventario_suficiente"])
            self.assertEqual(data["estado_inventario_general"], "AGOTADO")
            self.assertEqual(data["ninos_maximos_atendibles"], 0)
            self.assertIn("No hay alimentos disponibles", data["sugerencias"])
            self.assertEqual(len(data["ingredientes_agotados"]), 1)
            self.assertEqual(data["ingredientes_agotados"][0]["estado_stock"], "AGOTADO")
            for sug in data["sugerencias_ia_estructuradas"]:
                self.assertFalse(sug["viable_con_inventario"])
                self.assertEqual(sug["estado_inventario"], "AGOTADO")
                for ing in sug["ingredientes"]:
                    self.assertFalse(ing["alcanza"])
                    self.assertTrue(ing["agotado"])
                    self.assertEqual(ing["estado_stock"], "AGOTADO")

    def test_sin_id_sede_no_suma_inventario_de_otras_sedes(self):
        """Si no se especifica sede ni usuario con sede, no debe sumar inventarios de todas las sedes."""
        with patch("apps_sirae.ia_sugerencias.views.generar_con_openai", return_value=None):
            payload = {
                "ninos_presentes": 100,
                "id_seccion": 1,
                "generar_imagen": False,
            }
            response = self.client.post("/api/ia/sugerencias-recetas/", payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()

            self.assertFalse(data["inventario_suficiente"])
            self.assertEqual(data["estado_inventario_general"], "AGOTADO")
            self.assertEqual(data["resumen_inventario"]["total_productos_sede"], 0)

    def test_recetas_se_adaptan_solo_a_ingredientes_con_stock_suficiente(self):
        """La IA solo debe usar los ingredientes que alcanzan y excluir los insuficientes."""
        tomate = Ingrediente.objects.create(
            nombre_ingrediente="Tomate",
            id_unidad_medida=self.unidad_kg,
        )
        # 0.5 kg = 500 g -> a 20 g/niño solo cubre 25 niños, NO alcanza para 200
        Inventario.objects.create(
            id_sede=self.sede,
            id_institucion=self.institucion,
            id_ingrediente=tomate.id_ingrediente,
            cantidad_actual=Decimal("0.5"),
            stock_minimo=Decimal("1.0"),
            id_unidad_medida=self.unidad_kg.id_unidad_medida,
        )

        with patch("apps_sirae.ia_sugerencias.views.generar_con_openai", return_value=None):
            payload = {
                "id_sede": self.sede.id_sede,
                "ninos_presentes": 200,
                "id_seccion": 1,
                "generar_imagen": False,
            }
            response = self.client.post("/api/ia/sugerencias-recetas/", payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()

            self.assertTrue(data["inventario_suficiente"])
            self.assertTrue(len(data["sugerencias_ia_estructuradas"]) >= 1)
            for sug in data["sugerencias_ia_estructuradas"]:
                self.assertTrue(sug["viable_con_inventario"])
                self.assertEqual(sug["gastronomia"], "Colombiana PAE")
                nombres = [ing["nombre_ingrediente"].lower() for ing in sug["ingredientes"]]
                self.assertNotIn("tomate", nombres)
                for ing in sug["ingredientes"]:
                    self.assertTrue(ing["alcanza"])

            nombres_insuf = [i["nombre_ingrediente"].lower() for i in data["ingredientes_insuficientes"]]
            self.assertIn("tomate", nombres_insuf)

    def test_openai_con_ingredientes_inexistentes_es_descartado_y_adaptado(self):
        """Si OpenAI sugiere ingredientes que no existen en inventario, el validador los descarta."""
        respuesta_inviable = [
            {
                "nombre_plato": "Salmón con quinua y aguacate",
                "componentes_detalle": {"Alimento proteico": "Salmón"},
                "ingredientes_usados": ["Salmón", "Quinua", "Aguacate"],
                "pasos": ["Cocinar salmón."],
            }
        ]
        with patch("apps_sirae.ia_sugerencias.views.generar_con_openai", return_value=respuesta_inviable):
            payload = {
                "id_sede": self.sede.id_sede,
                "ninos_presentes": 200,
                "id_seccion": 1,
                "generar_imagen": False,
            }
            response = self.client.post("/api/ia/sugerencias-recetas/", payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()

            self.assertTrue(data["inventario_suficiente"])
            for sug in data["sugerencias_ia_estructuradas"]:
                self.assertNotIn("salmón", sug["nombre_plato"].lower())
                self.assertTrue(sug["viable_con_inventario"])
                for ing in sug["ingredientes"]:
                    self.assertTrue(ing["alcanza"])

    def test_generacion_y_subida_imagen_receta_colombiana_en_cloudinary(self):
        """Verifica que la sugerencia genere la imagen del plato colombiano y la guarde en Cloudinary."""
        from apps_sirae.ia_sugerencias import imagenes as mod_img

        mod_img._CACHE_IMAGENES.clear()
        fake_cloudinary_resp = {
            "secure_url": "https://res.cloudinary.com/sirae/image/upload/v1/sirae_ia_recetas/calentado.png",
            "public_id": "sirae_ia_recetas/calentado",
        }
        with patch("apps_sirae.ia_sugerencias.views.generar_con_openai", return_value=None), \
             patch("apps_sirae.ia_sugerencias.imagenes.cloudinary_configurado", return_value=True), \
             patch("apps_sirae.ia_sugerencias.imagenes._generar_bytes_openai", return_value=(None, None)), \
             patch("apps_sirae.ia_sugerencias.imagenes._generar_bytes_pollinations", return_value=(b"\x89PNG\r\n\x1a\n" + b"0" * 2048, "POLLINATIONS_IA")), \
             patch("apps_sirae.ia_sugerencias.imagenes.cloudinary.uploader.upload", return_value=fake_cloudinary_resp) as mock_upload:
            payload = {
                "id_sede": self.sede.id_sede,
                "ninos_presentes": 150,
                "id_seccion": 1,
                "generar_imagen": True,
            }
            response = self.client.post("/api/ia/sugerencias-recetas/", payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()

            self.assertTrue(len(data["sugerencias_ia_estructuradas"]) >= 1)
            sug = data["sugerencias_ia_estructuradas"][0]
            self.assertTrue(sug["guardada_en_cloudinary"])
            self.assertEqual(sug["imagen_url"], fake_cloudinary_resp["secure_url"])
            self.assertEqual(sug["imagen_cloudinary_public_id"], fake_cloudinary_resp["public_id"])
            self.assertEqual(sug["gastronomia"], "Colombiana PAE")
            mock_upload.assert_called_once()
            _, upload_kwargs = mock_upload.call_args
            self.assertEqual(upload_kwargs.get("folder"), "sirae_ia_recetas")

    def test_endpoint_dedicado_generar_imagen_receta_cloudinary(self):
        """Verifica el endpoint POST /api/ia/generar-imagen-receta/ guardando en Cloudinary."""
        from apps_sirae.ia_sugerencias import imagenes as mod_img

        mod_img._CACHE_IMAGENES.clear()
        fake_cloudinary_resp = {
            "secure_url": "https://res.cloudinary.com/sirae/image/upload/v1/sirae_ia_recetas/sudado_pollo.png",
            "public_id": "sirae_ia_recetas/sudado_pollo",
        }
        with patch("apps_sirae.ia_sugerencias.imagenes.cloudinary_configurado", return_value=True), \
             patch("apps_sirae.ia_sugerencias.imagenes._generar_bytes_openai", return_value=(None, None)), \
             patch("apps_sirae.ia_sugerencias.imagenes._generar_bytes_pollinations", return_value=(None, None)), \
             patch("apps_sirae.ia_sugerencias.imagenes.cloudinary.uploader.upload", return_value=fake_cloudinary_resp) as mock_upload:
            payload = {
                "nombre_plato": "Sudado criollo colombiano de pollo con papa y yuca",
                "seccion": "Almuerzo",
                "ingredientes": ["Pollo", "Papa", "Yuca", "Tomate", "Cebolla", "Arroz"],
            }
            response = self.client.post("/api/ia/generar-imagen-receta/", payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()

            self.assertEqual(data["status"], "success")
            self.assertTrue(data["guardada_en_cloudinary"])
            self.assertEqual(data["imagen_url"], fake_cloudinary_resp["secure_url"])
            self.assertEqual(data["imagen_origen"], "ILUSTRACION_COLOMBIANA_CLOUDINARY")
            mock_upload.assert_called_once()

    def test_imagen_nunca_es_nula_aunque_cloudinary_no_este_configurado(self):
        """Si Cloudinary no está configurado en el servidor, debe devolver igual una URL IA válida."""
        from apps_sirae.ia_sugerencias import imagenes as mod_img

        mod_img._CACHE_IMAGENES.clear()
        with patch("apps_sirae.ia_sugerencias.imagenes.cloudinary_configurado", return_value=False):
            payload = {
                "nombre_plato": "Ajiaco santafereño escolar de pollo",
                "seccion": "Almuerzo",
                "ingredientes": ["Pollo", "Papa", "Maíz", "Arroz"],
            }
            response = self.client.post("/api/ia/generar-imagen-receta/", payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()
            self.assertFalse(data["guardada_en_cloudinary"])
            self.assertTrue(str(data["imagen_url"]).startswith("https://image.pollinations.ai/prompt/"))
            self.assertEqual(data["imagen"], data["imagen_url"])



