from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
import re
import unicodedata

from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError

from apps_sirae.asistencia_diaria.models import AsistenciaDiaria
from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.entradas_inventario.models import EntradaInventario
from apps_sirae.entregas.models import Entrega
from apps_sirae.entregas.services import calcular_abastecimiento_sede
from apps_sirae.gramage.models import Gramage
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.instituciones.models import Institucion, SupervisorInstitucion
from apps_sirae.inventario.models import Inventario
from apps_sirae.inventario.services import obtener_resumen_asignaciones_institucion
from apps_sirae.preparacion_asignada.models import PreparacionAsignada
from apps_sirae.reportes.services.generador_planillas import _parse_fecha
from apps_sirae.salidas_inventario.models import SalidaInventario
from apps_sirae.sede_jornada.models import SedeJornada, SedeJornadaGrado
from apps_sirae.sedes.models import Sede
from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.unidades_medida.services import ErrorConversionUnidad, convertir_cantidad
from apps_sirae.usuarios.alcance import (
    describir_alcance_usuario,
    obtener_instituciones_autorizadas,
    obtener_sedes_autorizadas,
)
from apps_sirae.usuarios.models import Usuario


def _normalizar_texto(texto: str) -> str:
    txt = str(texto or '').strip().lower()
    return ''.join(
        c for c in unicodedata.normalize('NFD', txt)
        if unicodedata.category(c) != 'Mn'
    )


# Catálogo base oficial de formatos PAE (conserva todos los ítems y gramajes por defecto
# sobre los que se fusionan automáticamente los datos reales cargados por manipuladora/sede)
NO_PERECEDEROS_BASE = [
    {'alimento': 'ACEITE', 'gramajes': {'preescolar': 27, 'primaria13': 38, 'primaria45': 49, 'secundaria': 63, 'media': 77}, 'unidad': 'ml', 'baseMes': 59},
    {'alimento': 'PANELA', 'gramajes': {'preescolar': 40, 'primaria13': 40, 'primaria45': 50, 'secundaria': 60, 'media': 70}, 'unidad': 'g', 'baseMes': 34},
    {'alimento': 'ARROZ', 'gramajes': {'preescolar': 67, 'primaria13': 127, 'primaria45': 158, 'secundaria': 213, 'media': 247}, 'unidad': 'g', 'baseMes': 278},
    {'alimento': 'HARINA DE TRIGO', 'gramajes': {'preescolar': 42, 'primaria13': 42, 'primaria45': 54, 'secundaria': 81, 'media': 95}, 'unidad': 'g', 'baseMes': 24},
    {'alimento': 'PASTA', 'gramajes': {'preescolar': 32, 'primaria13': 40, 'primaria45': 50, 'secundaria': 60, 'media': 70}, 'unidad': 'g', 'baseMes': 21},
    {'alimento': 'CABELLO DE ÁNGEL', 'gramajes': {'preescolar': 5, 'primaria13': 5, 'primaria45': 7, 'secundaria': 10, 'media': 10}, 'unidad': 'g', 'baseMes': 12},
    {'alimento': 'AZÚCAR', 'gramajes': {'preescolar': 17, 'primaria13': 19, 'primaria45': 19, 'secundaria': 25, 'media': 25}, 'unidad': 'g', 'baseMes': 30},
    {'alimento': 'AVENA EN HOJUELAS', 'gramajes': {'preescolar': 22, 'primaria13': 12, 'primaria45': 15, 'secundaria': 15, 'media': 20}, 'unidad': 'g', 'baseMes': 24},
    {'alimento': 'SAL', 'gramajes': {'preescolar': 10, 'primaria13': 20, 'primaria45': 12, 'secundaria': 15, 'media': 20}, 'unidad': 'g', 'baseMes': 11},
    {'alimento': 'MANTEQUILLA', 'gramajes': {'preescolar': 3, 'primaria13': 4, 'primaria45': 6, 'secundaria': 6, 'media': 6}, 'unidad': 'g', 'baseMes': 7},
    {'alimento': 'HARINA DE MAÍZ AMARILLO', 'gramajes': {'preescolar': 40, 'primaria13': 40, 'primaria45': 50, 'secundaria': 60, 'media': 65}, 'unidad': 'g', 'baseMes': 21},
    {'alimento': 'POLVO DE HORNEAR', 'gramajes': {'preescolar': 0.5, 'primaria13': 0.5, 'primaria45': 0.5, 'secundaria': 0.5, 'media': 0.5}, 'unidad': 'g', 'baseMes': 227},
    {'alimento': 'MAYONESA', 'gramajes': {'preescolar': 0.5, 'primaria13': 0.5, 'primaria45': 0.5, 'secundaria': 0.5, 'media': 0.5}, 'unidad': 'g', 'baseMes': 114},
    {'alimento': 'BOLI QUESILLO / BOCADILLO', 'gramajes': {'preescolar': 30, 'primaria13': 30, 'primaria45': 30, 'secundaria': 30, 'media': 30}, 'unidad': 'UND', 'baseMes': 227},
    {'alimento': 'GALLETAS DULCES KRAKER', 'gramajes': {'preescolar': 50, 'primaria13': 50, 'primaria45': 50, 'secundaria': 60, 'media': 60}, 'unidad': 'UND', 'baseMes': 33},
    {'alimento': 'GALLETA SODA', 'gramajes': {'preescolar': 50, 'primaria13': 50, 'primaria45': 50, 'secundaria': 50, 'media': 50}, 'unidad': 'UND', 'baseMes': 227},
    {'alimento': 'AREQUIPE', 'gramajes': {'preescolar': 0.5, 'primaria13': 0.5, 'primaria45': 0.5, 'secundaria': 0.5, 'media': 0.5}, 'unidad': 'UND', 'baseMes': 7},
    {'alimento': 'CHOCOLATE EN AZÚCAR', 'gramajes': {'preescolar': 15, 'primaria13': 15, 'primaria45': 18, 'secundaria': 20, 'media': 20}, 'unidad': 'g', 'baseMes': 23},
    {'alimento': 'LENTEJA', 'gramajes': {'preescolar': 26, 'primaria13': 25, 'primaria45': 20, 'secundaria': 45, 'media': 53}, 'unidad': 'g', 'baseMes': 40},
    {'alimento': 'FRÍJOL', 'gramajes': {'preescolar': 16, 'primaria13': 25, 'primaria45': 30, 'secundaria': 45, 'media': 53}, 'unidad': 'g', 'baseMes': 27},
    {'alimento': 'YOGUR', 'gramajes': {'preescolar': 175, 'primaria13': 175, 'primaria45': 175, 'secundaria': 175, 'media': 175}, 'unidad': 'ml', 'baseMes': 227},
    {'alimento': 'LECHE LICUADA / LÍQUIDA', 'gramajes': {'preescolar': 100, 'primaria13': 100, 'primaria45': 100, 'secundaria': 100, 'media': 100}, 'unidad': 'ml', 'baseMes': 393},
]

PERECEDEROS_BASE = [
    {'alimento': 'CARNE CERDO', 'gramajes': {'preescolar': 40, 'primaria13': 40, 'primaria45': 50, 'secundaria': 70, 'media': 80}, 'unidad': 'g', 'baseSemanal': [0, 0, 10830, 0]},
    {'alimento': 'CARNE DE POLLO PECHUGA CON PIEL', 'gramajes': {'preescolar': 70, 'primaria13': 70, 'primaria45': 75, 'secundaria': 90, 'media': 90}, 'unidad': 'g', 'baseSemanal': [16945, 0, 16945, 16945]},
    {'alimento': 'CARNE DE RES', 'gramajes': {'preescolar': 50, 'primaria13': 50, 'primaria45': 60, 'secundaria': 80, 'media': 80}, 'unidad': 'g', 'baseSemanal': [0, 13100, 0, 0]},
    {'alimento': 'HUEVOS', 'gramajes': {'preescolar': 55, 'primaria13': 55, 'primaria45': 55, 'secundaria': 55, 'media': 55}, 'unidad': 'UND', 'baseSemanal': [454, 269.4, 227, 227]},
    {'alimento': 'PAPA (ACOMPAÑANTE)', 'gramajes': {'preescolar': 80, 'primaria13': 100, 'primaria45': 150, 'secundaria': 200, 'media': 250}, 'unidad': 'g', 'baseSemanal': [4.9, 4.9, 4.9, 34.1]},
    {'alimento': 'HABICHUELA', 'gramajes': {'preescolar': 10.5, 'primaria13': 12, 'primaria45': 12, 'secundaria': 20, 'media': 25}, 'unidad': 'g', 'baseSemanal': [0, 0, 3.0, 1.5]},
    {'alimento': 'VERDURA (CEBOLLA CABEZONA ACOMPAÑANTE)', 'gramajes': {'preescolar': 12.6, 'primaria13': 14.4, 'primaria45': 16.2, 'secundaria': 24.2, 'media': 29.2}, 'unidad': 'g', 'baseSemanal': [2.74, 1.3, 3.2, 4.0]},
    {'alimento': 'AJO CRUDO', 'gramajes': {'preescolar': 0.2, 'primaria13': 0.2, 'primaria45': 0.2, 'secundaria': 0.2, 'media': 0.2}, 'unidad': 'g', 'baseSemanal': [0, 45.4, 90.8, 0]},
    {'alimento': 'VERDURA (CEBOLLA JUNCA)', 'gramajes': {'preescolar': 3, 'primaria13': 3, 'primaria45': 6, 'secundaria': 6, 'media': 6}, 'unidad': 'g', 'baseSemanal': [0.99, 0, 0, 1.0]},
    {'alimento': 'VERDURA (TOMATE ACOMPAÑANTE)', 'gramajes': {'preescolar': 10, 'primaria13': 11, 'primaria45': 12, 'secundaria': 20, 'media': 20}, 'unidad': 'g', 'baseSemanal': [2.85, 1.5, 2.9, 5.7]},
    {'alimento': 'VERDURA (ZANAHORIA ACOMPAÑANTE)', 'gramajes': {'preescolar': 11, 'primaria13': 12, 'primaria45': 12, 'secundaria': 20, 'media': 25}, 'unidad': 'g', 'baseSemanal': [0, 0, 1.5, 1.5]},
    {'alimento': 'FRUTA (MANGO)', 'gramajes': {'preescolar': 220, 'primaria13': 220, 'primaria45': 240, 'secundaria': 240, 'media': 240}, 'unidad': 'g', 'baseSemanal': [0, 27.2, 27.2, 0]},
    {'alimento': 'FRUTA (GUAYABA MADURA)', 'gramajes': {'preescolar': 80, 'primaria13': 80, 'primaria45': 80, 'secundaria': 100, 'media': 133}, 'unidad': 'g', 'baseSemanal': [18.88, 0, 0, 0]},
    {'alimento': 'FRUTA (TOMATE DE ÁRBOL)', 'gramajes': {'preescolar': 75, 'primaria13': 75, 'primaria45': 75, 'secundaria': 75, 'media': 75}, 'unidad': 'g', 'baseSemanal': [17.03, 0, 0, 0]},
    {'alimento': 'FRUTA (MANDARINA)', 'gramajes': {'preescolar': 134, 'primaria13': 134, 'primaria45': 134, 'secundaria': 166, 'media': 166}, 'unidad': 'UND', 'baseSemanal': [0, 0, 227, 0]},
    {'alimento': 'FRUTA (PAPAYA)', 'gramajes': {'preescolar': 115, 'primaria13': 157, 'primaria45': 157, 'secundaria': 165, 'media': 200}, 'unidad': 'g', 'baseSemanal': [0, 35.6, 0, 35.6]},
    {'alimento': 'FRUTA (NARANJA)', 'gramajes': {'preescolar': 134, 'primaria13': 134, 'primaria45': 134, 'secundaria': 166, 'media': 166}, 'unidad': 'UND', 'baseSemanal': [0, 227, 0, 0]},
    {'alimento': 'FRUTA (MANZANA)', 'gramajes': {'preescolar': 129, 'primaria13': 129, 'primaria45': 129, 'secundaria': 153, 'media': 165}, 'unidad': 'UND', 'baseSemanal': [0, 0, 227, 0]},
    {'alimento': 'FRUTA (BANANO)', 'gramajes': {'preescolar': 100, 'primaria13': 157, 'primaria45': 157, 'secundaria': 185, 'media': 200}, 'unidad': 'UND', 'baseSemanal': [35.22, 0, 0, 0]},
]

ASEO_BASE = [
    {'item': 'Esponja plástica', 'unidad': 'Und', 'baseMes': 0},
    {'item': 'Jabón industrial (pH neutro)', 'unidad': '1000 CC', 'baseMes': 0},
    {'item': 'Esponja abrasiva (alambre)', 'unidad': 'Und', 'baseMes': 0},
    {'item': 'Papel higiénico', 'unidad': 'Und', 'baseMes': 0},
    {'item': 'Jabón líquido para manos', 'unidad': '250 CC', 'baseMes': 0},
    {'item': 'Desinfectante bucidí', 'unidad': '1000 CC', 'baseMes': 0},
    {'item': 'Bolsas plásticas biodegradables para residuos', 'unidad': 'Und', 'baseMes': 0},
]

KARDEX_ALIMENTOS_BASE = [
    {'alimento': 'VINAGRE', 'unidad': 'ml', 'entrada': 393, 'menu': 'Menú 1'},
    {'alimento': 'LECHE LÍQUIDA', 'unidad': 'ml', 'entrada': 7100, 'menu': 'Menú 1'},
    {'alimento': 'CARNE RES MAGRA', 'unidad': 'g', 'entrada': 11020, 'menu': 'Menú 2'},
    {'alimento': 'CARNE DE CERDO', 'unidad': 'g', 'entrada': 51720, 'menu': 'Menú 3'},
    {'alimento': 'CARNE DE POLLO, PECHUGA', 'unidad': 'g', 'entrada': 1198.3, 'menu': 'Menú 4'},
    {'alimento': 'HUEVOS', 'unidad': 'UND', 'entrada': 454, 'menu': 'Menú 1'},
    {'alimento': 'ORÉGANO', 'unidad': 'g', 'entrada': 49.9, 'menu': 'Condimento'},
    {'alimento': 'PAPA CRIOLLA', 'unidad': 'g', 'entrada': 11.4, 'menu': 'Acompañante'},
    {'alimento': 'PAPA (ACOMPAÑANTE)', 'unidad': 'g', 'entrada': 136.8, 'menu': 'Acompañante'},
    {'alimento': 'VERDURA (CEBOLLA CABEZONA)', 'unidad': 'g', 'entrada': 4.5, 'menu': 'Verdura'},
    {'alimento': 'AJO CRUDO', 'unidad': 'g', 'entrada': 2.0, 'menu': 'Condimento'},
    {'alimento': 'ESPINACA', 'unidad': 'g', 'entrada': 13.6, 'menu': 'Verdura'},
    {'alimento': 'VERDURA (APIO)', 'unidad': 'g', 'entrada': 3.0, 'menu': 'Verdura'},
    {'alimento': 'HABICHUELA', 'unidad': 'g', 'entrada': 55.4, 'menu': 'Verdura'},
    {'alimento': 'LECHUGA COMÚN', 'unidad': 'g', 'entrada': 15.0, 'menu': 'Verdura'},
    {'alimento': 'MAÍZ TIERNO', 'unidad': 'g', 'entrada': 20.0, 'menu': 'Verdura'},
    {'alimento': 'CILANTRO', 'unidad': 'g', 'entrada': 6.0, 'menu': 'Condimento'},
    {'alimento': 'REPOLLO BLANCO', 'unidad': 'g', 'entrada': 18.0, 'menu': 'Verdura'},
    {'alimento': 'VERDURA (CEBOLLA JUNCA)', 'unidad': 'g', 'entrada': 8.5, 'menu': 'Verdura'},
    {'alimento': 'PLÁTANO HARTÓN', 'unidad': 'g', 'entrada': 40.0, 'menu': 'Acompañante'},
    {'alimento': 'VERDURA (TOMATE ACOMPAÑANTE)', 'unidad': 'g', 'entrada': 25.0, 'menu': 'Verdura'},
    {'alimento': 'VERDURA (ZANAHORIA ACOMPAÑANTE)', 'unidad': 'g', 'entrada': 30.0, 'menu': 'Verdura'},
    {'alimento': 'PIMENTÓN VERDE', 'unidad': 'g', 'entrada': 12.0, 'menu': 'Verdura'},
    {'alimento': 'PIMENTÓN ROJO', 'unidad': 'g', 'entrada': 12.0, 'menu': 'Verdura'},
    {'alimento': 'AGUACATE', 'unidad': 'g', 'entrada': 35.0, 'menu': 'Acompañante'},
    {'alimento': 'PEPINO', 'unidad': 'g', 'entrada': 14.0, 'menu': 'Verdura'},
    {'alimento': 'GUASCAS CRUDAS', 'unidad': 'g', 'entrada': 4.0, 'menu': 'Condimento'},
    {'alimento': 'FRUTA (MANGO)', 'unidad': 'g', 'entrada': 60.0, 'menu': 'Fruta'},
    {'alimento': 'FRUTA (LULO)', 'unidad': 'g', 'entrada': 45.0, 'menu': 'Fruta'},
]

_ALIASES_ALIMENTOS = {
    'carne cerdo': 'carne cerdo',
    'carne de cerdo': 'carne cerdo',
    'cerdo': 'carne cerdo',
    'carne de pollo pechuga con piel': 'carne pollo pechuga',
    'carne de pollo pechuga': 'carne pollo pechuga',
    'carne pollo pechuga': 'carne pollo pechuga',
    'carne de pollo': 'carne pollo pechuga',
    'pechuga de pollo': 'carne pollo pechuga',
    'pechuga': 'carne pollo pechuga',
    'pollo': 'carne pollo pechuga',
    'carne de res': 'carne res',
    'carne res magra': 'carne res',
    'carne de res magra': 'carne res',
    'carne res': 'carne res',
    'res': 'carne res',
    'huevos': 'huevos',
    'huevo': 'huevos',
    'huevo aa': 'huevos',
    'leche licuada liquida': 'leche liquida',
    'leche liquida': 'leche liquida',
    'leche licuada': 'leche liquida',
    'leche entera': 'leche liquida',
    'leche': 'leche liquida',
    'boli quesillo bocadillo': 'boli quesillo bocadillo',
    'bocadillo': 'boli quesillo bocadillo',
    'quesillo': 'boli quesillo bocadillo',
    'galletas dulces kraker': 'galletas dulces kraker',
    'galleta dulce kraker': 'galletas dulces kraker',
    'galleta kraker': 'galletas dulces kraker',
    'galleta soda': 'galleta soda',
    'galletas soda': 'galleta soda',
    'harina de trigo': 'harina trigo',
    'harina trigo': 'harina trigo',
    'harina de maiz amarillo': 'harina maiz amarillo',
    'harina de maiz': 'harina maiz amarillo',
    'harina maiz': 'harina maiz amarillo',
    'chocolate en azucar': 'chocolate azucar',
    'chocolate': 'chocolate azucar',
    'lenteja': 'lenteja',
    'lentejas': 'lenteja',
    'frijol': 'frijol',
    'frijoles': 'frijol',
    'yogur': 'yogur',
    'yogurt': 'yogur',
    'papa criolla': 'papa criolla',
    'papa acompanante': 'papa acompanante',
    'papa': 'papa acompanante',
    'cebolla cabezona acompanante': 'cebolla cabezona',
    'cebolla cabezona': 'cebolla cabezona',
    'cebolla junca': 'cebolla junca',
    'cebolla larga': 'cebolla junca',
    'tomate de arbol': 'tomate de arbol',
    'tomate arbol': 'tomate de arbol',
    'tomate acompanante': 'tomate acompanante',
    'tomate': 'tomate acompanante',
    'tomate chonto': 'tomate acompanante',
    'zanahoria acompanante': 'zanahoria',
    'zanahoria': 'zanahoria',
    'ajo crudo': 'ajo',
    'ajo': 'ajo',
    'apio': 'apio',
    'mango': 'mango',
    'guayaba madura': 'guayaba',
    'guayaba': 'guayaba',
    'mandarina': 'mandarina',
    'papaya': 'papaya',
    'naranja': 'naranja',
    'manzana': 'manzana',
    'banano': 'banano',
    'lulo': 'lulo',
    'platano harton': 'platano harton',
    'guasquas crudas': 'guascas crudas',
    'guascas crudas': 'guascas crudas',
    'guascas': 'guascas crudas',
    'repollo blanco': 'repollo blanco',
    'lechuga comun': 'lechuga comun',
    'lechuga': 'lechuga comun',
    'pimenton verde': 'pimenton verde',
    'pimenton rojo': 'pimenton rojo',
    'jabon industrial ph neutro': 'jabon industrial ph neutro',
    'jabon industrial': 'jabon industrial ph neutro',
    'jabon liquido para manos': 'jabon liquido para manos',
    'jabon liquido': 'jabon liquido para manos',
    'desinfectante bucidi': 'desinfectante bucidi',
    'desinfectante': 'desinfectante bucidi',
    'esponja plastica': 'esponja plastica',
    'esponja abrasiva alambre': 'esponja abrasiva alambre',
    'esponja abrasiva': 'esponja abrasiva alambre',
    'papel higienico': 'papel higienico',
    'bolsas plasticas biodegradables para residuos': 'bolsas plasticas biodegradables para residuos',
    'bolsas biodegradables': 'bolsas plasticas biodegradables para residuos',
    'bolsas de basura': 'bolsas plasticas biodegradables para residuos',
}

_PALABRAS_ENVOLTORIO = {'fruta', 'verdura', 'acompanante', 'de', 'en', 'con', 'para', 'piel'}


def _limpiar_clave_alimento(nombre: str) -> str:
    txt = _normalizar_texto(nombre)
    txt = re.sub(r'[()/,\.\-]+', ' ', txt)
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt


def _claves_alimento(nombre: str) -> list[str]:
    limpio = _limpiar_clave_alimento(nombre)
    if not limpio:
        return []
    sin_envoltorio = ' '.join(t for t in limpio.split() if t not in _PALABRAS_ENVOLTORIO).strip()
    candidatos = []
    for k in (limpio, sin_envoltorio):
        if not k:
            continue
        canon = _ALIASES_ALIMENTOS.get(k, k)
        if canon not in candidatos:
            candidatos.append(canon)
        if k not in candidatos:
            candidatos.append(k)
    return candidatos


def _buscar_ingrediente_coincidente(
    nombre_base: str,
    ing_ids_candidatos: list[int],
    ingredientes_map: dict,
    claves_por_ing: dict,
    ya_emparejados: set,
) -> int | None:
    claves_base = _claves_alimento(nombre_base)
    if not claves_base:
        return None
    canon_base = claves_base[0]

    # 1. Coincidencia exacta por alias canónico o nombre normalizado completo
    for ing_id in ing_ids_candidatos:
        if ing_id in ya_emparejados:
            continue
        claves_ing = claves_por_ing.get(ing_id, [])
        if any(cb in claves_ing for cb in claves_base):
            return ing_id

    # 2. Coincidencia por palabra inicial cuando es producto simple (ej. "arroz blanco" -> "arroz")
    tokens_base = [t for t in canon_base.split() if len(t) >= 3]
    if len(tokens_base) == 1:
        tok = tokens_base[0]
        for ing_id in ing_ids_candidatos:
            if ing_id in ya_emparejados:
                continue
            claves_ing = claves_por_ing.get(ing_id, [])
            if any(ci.split()[0] == tok for ci in claves_ing if ci.split()):
                # Evitar falsos positivos conocidos (harina, pimentón, tomate, papa, cebolla)
                if tok in {'harina', 'pimenton', 'tomate', 'papa', 'cebolla', 'carne', 'jabon', 'esponja', 'galleta'}:
                    continue
                return ing_id
    return None


def _fusionar_gramajes(base_gramajes: dict, db_gramajes: dict | None) -> dict:
    niveles = ('preescolar', 'primaria13', 'primaria45', 'secundaria', 'media')
    if not db_gramajes:
        return {k: float(base_gramajes.get(k, 0)) for k in niveles}
    return {
        k: (float(db_gramajes[k]) if float(db_gramajes.get(k) or 0) > 0 else float(base_gramajes.get(k, 0)))
        for k in niveles
    }


def _fecha_local(valor) -> date | None:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        if timezone.is_aware(valor):
            return timezone.localdate(valor)
        return valor.date()
    if isinstance(valor, date):
        return valor
    return _parse_fecha(str(valor))


def _rango_fechas_por_defecto(fecha_inicio_raw, fecha_fin_raw) -> tuple[date, date]:
    hoy = timezone.localdate()
    fecha_fin = _parse_fecha(fecha_fin_raw)
    fecha_inicio = _parse_fecha(fecha_inicio_raw)

    if fecha_inicio and not fecha_fin:
        # Avanzar hasta cubrir 20 días hábiles desde fecha_inicio
        actual = fecha_inicio
        habiles = 0
        while habiles < 20:
            if actual.weekday() < 5:
                habiles += 1
            if habiles < 20:
                actual += timedelta(days=1)
        fecha_fin = actual
    elif fecha_fin and not fecha_inicio:
        actual = fecha_fin
        habiles = 0
        while habiles < 20:
            if actual.weekday() < 5:
                habiles += 1
            if habiles < 20:
                actual -= timedelta(days=1)
        fecha_inicio = actual
    elif not fecha_inicio and not fecha_fin:
        fecha_fin = hoy
        actual = hoy
        habiles = 0
        while habiles < 20:
            if actual.weekday() < 5:
                habiles += 1
            if habiles < 20:
                actual -= timedelta(days=1)
        fecha_inicio = actual

    if fecha_inicio > fecha_fin:
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

    return fecha_inicio, fecha_fin


def _generar_dias_habiles(fecha_inicio: date, fecha_fin: date) -> list[date]:
    dias = []
    actual = fecha_inicio
    while actual <= fecha_fin:
        if actual.weekday() < 5:
            dias.append(actual)
        actual += timedelta(days=1)
    if not dias:
        dias.append(fecha_inicio)
    return dias


def _clasificar_grupo_ingrediente(ingrediente: Ingrediente | None, nombre_tipo: str = '', nombre_categoria: str = '') -> str:
    """
    Clasifica un ingrediente real de SIRAE en:
    - 'ASEO'
    - 'PERECEDERO'
    - 'NO_PERECEDERO'
    """
    cat_txt = _normalizar_texto(
        nombre_categoria
        or (ingrediente.id_categoria_inventario.nombre_categoria if ingrediente and ingrediente.id_categoria_inventario else '')
    )
    tm_txt = _normalizar_texto(
        nombre_tipo
        or (ingrediente.id_tipo_mercado.nombre_tipo if ingrediente and ingrediente.id_tipo_mercado else '')
    )
    combinado = f"{cat_txt} {tm_txt}"
    if any(pal in combinado for pal in ('aseo', 'limpieza', 'higiene', 'desinfect', 'desinfeccion')):
        return 'ASEO'

    tc = _normalizar_texto(getattr(ingrediente, 'tipo_conservacion', '') if ingrediente else '')
    if tc == 'perecedero':
        return 'PERECEDERO'
    if tc in {'no_perecedero', 'no perecedero'}:
        return 'NO_PERECEDERO'
    if 'perecedero' in tm_txt and 'no perecedero' not in tm_txt and 'no_perecedero' not in tm_txt:
        return 'PERECEDERO'
    return 'NO_PERECEDERO'


def _clasificar_nivel_cupos(nivel_educativo: str, nombre_grado: str) -> str:
    niv = _normalizar_texto(nivel_educativo).upper()
    nom = _normalizar_texto(nombre_grado)

    if niv == 'PREESCOLAR' or any(p in nom for p in ('preescolar', 'transicion', 'jardin', 'prejardin')):
        return 'preescolar'
    if niv == 'PRIMARIA':
        if any(p in nom for p in ('4', 'cuarto', '5', 'quinto')):
            return 'primaria45'
        return 'primaria13'
    if niv == 'SECUNDARIA':
        return 'secundaria'
    if niv == 'MEDIA':
        return 'media'
    if any(p in nom for p in ('10', 'decimo', '11', 'once')):
        return 'media'
    if any(p in nom for p in ('6', 'sexto', '7', 'septimo', '8', 'octavo', '9', 'noveno')):
        return 'secundaria'
    if any(p in nom for p in ('4', 'cuarto', '5', 'quinto')):
        return 'primaria45'
    if any(p in nom for p in ('1', 'primero', '2', 'segundo', '3', 'tercero')):
        return 'primaria13'
    return 'otro'


def _serializar_persona(usuario: Usuario) -> dict:
    rol_nombre = ''
    if usuario.rol_id and usuario.rol:
        rol_nombre = usuario.rol.nombre
    return {
        'id_usuario': usuario.id_usuario,
        'nombre_completo': usuario.nombre_completo,
        'numero_documento': usuario.numero_documento or '',
        'correo': usuario.correo or '',
        'rol': rol_nombre,
        'id_sede': usuario.id_sede_id,
        'sede_nombre': usuario.id_sede.nombre_sede if usuario.id_sede_id else '',
        'id_jornada': usuario.id_jornada_id,
    }


def _dedup_personas(personas: list[dict]) -> list[dict]:
    vistas = set()
    resultado = []
    for p in personas:
        uid = p.get('id_usuario')
        if uid in vistas:
            continue
        vistas.add(uid)
        resultado.append(p)
    return resultado


def _convertir_a_unidad(
    cantidad: Decimal,
    unidad_origen: UnidadMedida | None,
    unidad_destino: UnidadMedida | None,
    ingrediente: Ingrediente | None = None,
) -> Decimal:
    if cantidad == 0 or not unidad_origen or not unidad_destino or unidad_origen.pk == unidad_destino.pk:
        return cantidad
    try:
        return convertir_cantidad(cantidad, unidad_origen, unidad_destino, ingrediente=ingrediente)
    except ErrorConversionUnidad:
        return cantidad


def _resolver_institucion_y_sedes(usuario: Usuario, id_institucion_raw, id_sede_raw):
    instituciones_auth = obtener_instituciones_autorizadas(usuario).order_by('nombre_institucion')
    sedes_auth = obtener_sedes_autorizadas(usuario).select_related('id_institucion').order_by('nombre_sede')

    id_inst = None
    if id_institucion_raw not in (None, '', 'null', 'undefined'):
        try:
            id_inst = int(id_institucion_raw)
        except (TypeError, ValueError):
            raise DRFValidationError({'id_institucion': 'Identificador de institución inválido.'})
        institucion = instituciones_auth.filter(id_institucion=id_inst).first()
        if not institucion:
            raise PermissionDenied('No tiene autorización para consultar esta institución.')
    else:
        institucion = None

    id_sede = None
    sede_sel = None
    if id_sede_raw not in (None, '', 'null', 'undefined', 'Todas', 'todas', 'TODAS'):
        try:
            id_sede = int(id_sede_raw)
        except (TypeError, ValueError):
            raise DRFValidationError({'id_sede': 'Identificador de sede inválido.'})
        sede_sel = sedes_auth.filter(id_sede=id_sede).first()
        if not sede_sel:
            raise PermissionDenied('No tiene autorización para consultar esta sede.')
        if institucion and sede_sel.id_institucion_id != institucion.id_institucion:
            raise PermissionDenied('La sede seleccionada no pertenece a la institución activa.')
        if not institucion:
            institucion = sede_sel.id_institucion

    if not institucion:
        institucion = instituciones_auth.first()

    if not institucion:
        return None, None, [], []

    sedes_inst = list(sedes_auth.filter(id_institucion_id=institucion.id_institucion))
    sedes_objetivo = [sede_sel] if sede_sel else sedes_inst
    return institucion, sede_sel, sedes_objetivo, sedes_inst


def construir_datos_plantillas_operativas(usuario: Usuario, params: dict) -> dict:
    """
    Recopila y estructura en tiempo real todos los datos reales de SIRAE para
    las planillas operativas (Remisión, Kárdex y Minuta Patrón) acotados
    estrictamente a la institución y sede seleccionada.
    """
    fecha_inicio, fecha_fin = _rango_fechas_por_defecto(
        params.get('fecha_inicio'), params.get('fecha_fin')
    )
    dias_habiles = _generar_dias_habiles(fecha_inicio, fecha_fin)
    dias_iso = [d.isoformat() for d in dias_habiles]
    dias_periodo = max(1, len(dias_habiles))

    institucion, sede_sel, sedes_objetivo, sedes_inst = _resolver_institucion_y_sedes(
        usuario, params.get('id_institucion'), params.get('id_sede')
    )

    if not institucion:
        return {
            'sin_alcance': True,
            'institucion': None,
            'sede': None,
            'sedes_disponibles': [],
            'contrato': None,
            'encabezado': {
                'departamento': '',
                'municipio': '',
                'entidad_territorial': '',
                'nombre_institucion': '',
                'nombre_sede': '',
                'codigo_dane': '',
                'operador': '',
                'numero_contrato': '',
                'telefono': '',
                'direccion': '',
                'fecha_inicio': fecha_inicio.isoformat(),
                'fecha_fin': fecha_fin.isoformat(),
                'dias_atender': dias_periodo,
            },
            'cupos': {
                'total': 0,
                'preescolar': 0,
                'primaria13': 0,
                'primaria45': 0,
                'secundaria': 0,
                'media': 0,
                'otro': 0,
                'origen': 'SIN_CONFIGURAR',
                'detalle_grados': [],
            },
            'responsables': {
                'manipuladora_jefe': None,
                'manipuladora': None,
                'manipuladoras': [],
                'jefas_manipuladoras': [],
                'administrador': None,
                'administradores': [],
                'supervisor': None,
                'supervisores': [],
                'receptor_entrega': None,
            },
            'remision': {'no_perecederos': [], 'perecederos': [], 'aseo': []},
            'kardex': {
                'dias': dias_iso,
                'raciones_dia': [0 for _ in dias_iso],
                'total_atendido': 0,
                'alimentos': [],
            },
            'minuta_patron': [],
            'resumen_actividad': {
                'entregas_count': 0,
                'salidas_count': 0,
                'entradas_count': 0,
                'asistencias_count': 0,
            },
            'alcance': describir_alcance_usuario(usuario),
        }

    sedes_ids = [s.id_sede for s in sedes_objetivo]

    # ---------- CONTRATO REAL ----------
    contratos_qs = (
        Contrato.objects.filter(
            Q(id_sede_id__in=sedes_ids)
            | Q(id_institucion_id=institucion.id_institucion, id_sede__isnull=True)
        )
        .select_related('id_usuario_supervisor', 'id_sede', 'id_jornada')
        .order_by('-fecha_inicio', '-id_contrato')
    )
    contratos_lista = sorted(
        list(contratos_qs),
        key=lambda c: (
            0 if str(c.estado or '').strip().upper() in {'ACTIVO', 'VIGENTE', 'EN_EJECUCION'} else 1,
            0 if (sede_sel and c.id_sede_id == sede_sel.id_sede) else 1,
            -(c.fecha_inicio.toordinal() if c.fecha_inicio else 0),
            -c.id_contrato,
        ),
    )
    contrato_principal = contratos_lista[0] if contratos_lista else None

    # ---------- RESPONSABLES REALES (ESTRICTAMENTE ACOTADOS A LA SEDE) ----------
    # Usuarios vinculados explícitamente a la(s) sede(s) objetivo
    usuarios_sede_exacta = list(
        Usuario.objects.filter(id_sede_id__in=sedes_ids, is_active=True)
        .select_related('rol', 'id_sede', 'id_jornada')
        .order_by('id_usuario')
    )
    # Usuarios asignados a la institución sin sede (p. ej. Administrador, o Jefa en colegio de 1 sola sede)
    usuarios_inst_sin_sede = list(
        Usuario.objects.filter(
            id_institucion_id=institucion.id_institucion,
            id_sede__isnull=True,
            is_active=True,
        )
        .select_related('rol', 'id_sede', 'id_jornada')
        .order_by('id_usuario')
    )

    incluir_inst_sin_sede_en_cocina = (not sede_sel) or (len(sedes_inst) <= 1)
    candidatos_cocina = list(usuarios_sede_exacta)
    if incluir_inst_sin_sede_en_cocina:
        candidatos_cocina.extend(usuarios_inst_sin_sede)

    jefas_manipuladoras = _dedup_personas(
        [_serializar_persona(u) for u in candidatos_cocina if u.es_jefa_manipuladoras()]
    )
    manipuladoras = _dedup_personas(
        [_serializar_persona(u) for u in candidatos_cocina if u.es_manipuladora()]
    )

    usuarios_inst_todos = list(
        Usuario.objects.filter(id_institucion_id=institucion.id_institucion, is_active=True)
        .select_related('rol', 'id_sede')
        .order_by('id_usuario')
    )
    administradores = _dedup_personas(
        [_serializar_persona(u) for u in usuarios_inst_todos if u.es_administrador()]
    )

    supervisores_objs = []
    if contrato_principal and contrato_principal.id_usuario_supervisor and contrato_principal.id_usuario_supervisor.is_active:
        supervisores_objs.append(contrato_principal.id_usuario_supervisor)
    for rel in SupervisorInstitucion.objects.filter(id_institucion=institucion).select_related(
        'id_supervisor', 'id_supervisor__rol', 'id_supervisor__id_sede'
    ):
        if rel.id_supervisor and rel.id_supervisor.is_active:
            supervisores_objs.append(rel.id_supervisor)
    if usuario.es_supervisor() and usuario.is_active:
        supervisores_objs.append(usuario)
    supervisores = _dedup_personas([_serializar_persona(u) for u in supervisores_objs])

    # Priorizar a quienes realmente hayan registrado entregas/asistencia/preparaciones en esta sede y periodo
    sedes_id_set = set(sedes_ids)
    usuarios_mov_ids = {u.id_usuario for u in usuarios_sede_exacta}
    if not sede_sel or len(sedes_inst) <= 1:
        usuarios_mov_ids.update(u.id_usuario for u in usuarios_inst_sin_sede)
    if len(sedes_inst) <= 1 and len(list(obtener_instituciones_autorizadas(usuario))) <= 1:
        usuarios_mov_ids.update(u.id_usuario for u in supervisores_objs)

    # ---------- CUPOS REALES POR GRADO Y NIVEL ----------
    sede_jornadas = list(
        SedeJornada.objects.filter(id_sede_id__in=sedes_ids)
        .select_related('id_sede', 'id_jornada')
    )
    sj_ids = [sj.id_sede_jornada for sj in sede_jornadas]
    sj_grados = list(
        SedeJornadaGrado.objects.filter(id_sede_jornada_id__in=sj_ids, estado='ACTIVO')
        .select_related(
            'id_grado',
            'id_grado__id_grupo_gramaje',
            'id_sede_jornada',
            'id_sede_jornada__id_sede',
            'id_sede_jornada__id_jornada',
        )
    )

    cupos_nivel = {
        'preescolar': 0,
        'primaria13': 0,
        'primaria45': 0,
        'secundaria': 0,
        'media': 0,
        'otro': 0,
    }
    cupos_por_grado_id = defaultdict(int)
    grado_nivel_map = {}
    detalle_grados = []

    for rel in sj_grados:
        grado = rel.id_grado
        if not grado or grado.estado == 'INACTIVO':
            continue
        cant = int(rel.cupos or 0)
        niv_key = _clasificar_nivel_cupos(grado.nivel_educativo, grado.nombre_grado)
        cupos_nivel[niv_key] += cant
        cupos_por_grado_id[grado.id_grado] += cant
        grado_nivel_map[grado.id_grado] = niv_key
        detalle_grados.append({
            'id_sede': rel.id_sede_jornada.id_sede_id,
            'nombre_sede': rel.id_sede_jornada.id_sede.nombre_sede if rel.id_sede_jornada.id_sede else '',
            'id_jornada': rel.id_sede_jornada.id_jornada_id,
            'nombre_jornada': rel.id_sede_jornada.id_jornada.nombre_jornada if rel.id_sede_jornada.id_jornada else '',
            'id_grado': grado.id_grado,
            'nombre_grado': grado.nombre_grado,
            'nivel_educativo': grado.nivel_educativo,
            'cupos': cant,
        })

    total_cupos_grados = sum(cupos_nivel.values())
    if total_cupos_grados > 0:
        total_cupos = total_cupos_grados
        origen_cupos = 'SEDE_JORNADA_GRADO'
    else:
        total_sj = sum(int(sj.cupos or 0) for sj in sede_jornadas)
        if total_sj > 0:
            total_cupos = total_sj
            origen_cupos = 'SEDE_JORNADA'
        elif contrato_principal and contrato_principal.cupos:
            total_cupos = int(contrato_principal.cupos or 0)
            origen_cupos = 'CONTRATO'
        else:
            total_cupos = 0
            origen_cupos = 'SIN_CONFIGURAR'

    # ---------- ENTREGAS REALES ----------
    entregas_qs = Entrega.objects.filter(
        Q(fecha_entrega__range=(fecha_inicio, fecha_fin))
        | Q(fecha_recepcion__date__range=(fecha_inicio, fecha_fin)),
        id_institucion_id=institucion.id_institucion,
    ).select_related('id_usuario_receptor', 'id_sede', 'id_contrato')
    if sede_sel:
        entregas_qs = entregas_qs.filter(id_sede_id=sede_sel.id_sede)
    elif sedes_ids:
        entregas_qs = entregas_qs.filter(Q(id_sede_id__in=sedes_ids) | Q(id_sede__isnull=True))

    entregas_lista = list(entregas_qs.order_by('fecha_entrega', 'id_entrega'))

    receptor_entrega = None
    for ent in reversed(entregas_lista):
        if ent.id_usuario_receptor and ent.id_usuario_receptor.is_active:
            if not sede_sel or ent.id_usuario_receptor.id_sede_id in (None, sede_sel.id_sede):
                receptor_entrega = _serializar_persona(ent.id_usuario_receptor)
                break

    # ---------- ENTRADAS Y SALIDAS REALES DE INVENTARIO ----------
    entradas_qs = EntradaInventario.objects.filter(
        fecha__isnull=False,
        id_usuario_id__in=usuarios_mov_ids,
    ).select_related('id_ingrediente', 'id_ingrediente__id_unidad_medida', 'id_unidad_medida')
    entradas_lista = [
        e for e in entradas_qs
        if (fl := _fecha_local(e.fecha)) is not None and fecha_inicio <= fl <= fecha_fin
    ]

    salidas_qs = SalidaInventario.objects.filter(
        fecha__isnull=False,
        id_usuario_id__in=usuarios_mov_ids,
    ).select_related('id_ingrediente', 'id_ingrediente__id_unidad_medida', 'id_unidad_medida', 'id_usuario')
    salidas_lista = [
        s for s in salidas_qs
        if (fl := _fecha_local(s.fecha)) is not None and fecha_inicio <= fl <= fecha_fin
    ]

    # ---------- ASISTENCIA DIARIA REAL (SIN MULTIPLICADORES FALSOS) ----------
    usuarios_inst_sin_sede_ids = {u.id_usuario for u in usuarios_inst_sin_sede}
    grados_sede_ids = set(cupos_por_grado_id.keys())
    asistencia_q = Q(id_usuario_manipuladora__in=usuarios_mov_ids)
    if grados_sede_ids and usuarios_inst_sin_sede_ids:
        asistencia_q |= Q(
            id_grado_id__in=grados_sede_ids,
            id_usuario_manipuladora__in=usuarios_inst_sin_sede_ids,
        )
    asistencia_qs = AsistenciaDiaria.objects.filter(
        asistencia_q,
        fecha__range=(fecha_inicio, fecha_fin),
    ).select_related('id_grado')
    asistencia_lista = list(asistencia_qs)

    asistencia_por_fecha = defaultdict(int)
    for a in asistencia_lista:
        asistencia_por_fecha[a.fecha] += int(a.ninos_presentes or 0)

    raciones_dia = [asistencia_por_fecha.get(d, 0) for d in dias_habiles]

    # Enriquecer persona activa por preparaciones o asistencias del periodo
    prep_qs = PreparacionAsignada.objects.filter(
        id_usuario_manipuladora_id__in=usuarios_mov_ids,
        fecha__range=(fecha_inicio, fecha_fin),
    ).select_related('id_usuario_manipuladora', 'id_usuario_manipuladora__rol', 'id_usuario_manipuladora__id_sede')
    manip_ids_activas = {p.id_usuario_manipuladora_id for p in prep_qs if p.id_usuario_manipuladora_id}
    manip_ids_activas.update(a.id_usuario_manipuladora for a in asistencia_lista if a.id_usuario_manipuladora)

    if manip_ids_activas:
        manipuladoras.sort(key=lambda m: (0 if m['id_usuario'] in manip_ids_activas else 1, m['id_usuario']))
        jefas_manipuladoras.sort(key=lambda j: (0 if j['id_usuario'] in manip_ids_activas else 1, j['id_usuario']))

    # ---------- UNIDADES DE MEDIDA Y CATÁLOGO DE INGREDIENTES ----------
    unidades_lista = list(UnidadMedida.objects.all())
    unidades_by_id = {u.id_unidad_medida: u for u in unidades_lista}
    unidades_by_key = {}
    for u in unidades_lista:
        if u.abreviatura:
            unidades_by_key[_normalizar_texto(u.abreviatura)] = u
        if u.nombre:
            unidades_by_key[_normalizar_texto(u.nombre)] = u

    unidad_g = unidades_by_key.get('g') or unidades_by_key.get('gramo')
    unidad_kg = unidades_by_key.get('kg') or unidades_by_key.get('kilogramo')

    # ---------- ABASTECIMIENTO HU5 PROGRAMADO POR SEDE ----------
    dias_cobertura_per = (
        int(contrato_principal.dias_cobertura_perecederos or 5)
        if contrato_principal else 5
    )
    dias_cobertura_no_per = dias_periodo

    programado_por_ing = defaultdict(lambda: {
        'id_ingrediente': None,
        'nombre_ingrediente': '',
        'cantidad_periodo': Decimal('0'),
        'cantidad_semanal': Decimal('0'),
        'unidad_abreviatura': '',
        'grupo': 'NO_PERECEDERO',
        'frecuencia': '',
        'porcion_gramaje': Decimal('0'),
        'dias_periodo': dias_periodo,
    })

    for sede in sedes_objetivo:
        try:
            calc = calcular_abastecimiento_sede(
                sede,
                dias_perecederos_override=min(dias_cobertura_per, dias_periodo),
                dias_no_perecederos_override=dias_cobertura_no_per,
                id_contrato=contrato_principal.id_contrato if contrato_principal else None,
                incluir_todos_gramajes=True,
            )
            sugerencias = calc.get('productos_sugeridos') or calc.get('sugerencias_entrega') or []
        except Exception:
            sugerencias = []

        for sug in sugerencias:
            ing_id = sug.get('id_ingrediente')
            if not ing_id:
                continue
            item = programado_por_ing[ing_id]
            item['id_ingrediente'] = ing_id
            item['nombre_ingrediente'] = sug.get('nombre_ingrediente') or item['nombre_ingrediente']
            cant_req = Decimal(str(sug.get('cantidad_total_requerida') or 0))
            es_per = bool(sug.get('es_perecedero'))
            if es_per:
                item['cantidad_semanal'] += cant_req
                semanas = max(Decimal('1'), Decimal(dias_periodo) / Decimal('5'))
                item['cantidad_periodo'] += (cant_req * semanas)
                item['frecuencia'] = sug.get('periodicidad_aplicada') or 'SEMANAL'
            else:
                item['cantidad_periodo'] += cant_req
                item['frecuencia'] = sug.get('periodicidad_aplicada') or 'MENSUAL'
            item['unidad_abreviatura'] = sug.get('unidad_abreviatura') or sug.get('unidad_medida') or item['unidad_abreviatura']
            item['porcion_gramaje'] = Decimal(str(sug.get('porcion_gramaje') or item['porcion_gramaje'] or 0))

    # Inventario actual en sede(s)
    inv_qs = Inventario.objects.all()
    if sede_sel:
        inv_qs = inv_qs.filter(id_sede_id=sede_sel.id_sede)
    else:
        inv_qs = inv_qs.filter(
            Q(id_sede_id__in=sedes_ids)
            | Q(id_institucion_id=institucion.id_institucion, id_sede__isnull=True)
        )
    inventario_sede_map = defaultdict(Decimal)
    inventario_unidad_map = {}
    for inv in inv_qs:
        inventario_sede_map[inv.id_ingrediente] += Decimal(str(inv.cantidad_actual or 0))
        inventario_unidad_map.setdefault(inv.id_ingrediente, inv.id_unidad_medida)

    asig_resumen = obtener_resumen_asignaciones_institucion(
        institucion.id_institucion,
        solo_activas=False,
    )
    asig_inst_map = asig_resumen.get('mapa_por_ingrediente') or {}

    # Reunir todos los ingredientes involucrados en esta sede/periodo
    ing_ids_relevantes = set(programado_por_ing.keys())
    ing_ids_relevantes.update(e.id_ingrediente for e in entregas_lista if e.id_ingrediente)
    ing_ids_relevantes.update(ent.id_ingrediente_id for ent in entradas_lista if ent.id_ingrediente_id)
    ing_ids_relevantes.update(sal.id_ingrediente_id for sal in salidas_lista if sal.id_ingrediente_id)
    ing_ids_relevantes.update(inventario_sede_map.keys())
    ing_ids_relevantes.update(asig_inst_map.keys())

    # Gramajes activos para grados atendidos en sede -> alimenta también Minuta Patrón
    gramajes_activos = list(
        Gramage.objects.filter(estado='ACTIVO')
        .select_related(
            'id_ingrediente',
            'id_ingrediente__id_categoria_inventario',
            'id_ingrediente__id_tipo_mercado',
            'id_ingrediente__id_unidad_medida',
            'id_unidad_medida',
            'id_grado',
        )
        .order_by('id_ingrediente__nombre_ingrediente', '-id_gramaje')
    )
    grados_atendidos_ids = set(cupos_por_grado_id.keys())
    for g in gramajes_activos:
        if g.id_ingrediente_id and (not grados_atendidos_ids or g.id_grado_id in grados_atendidos_ids):
            ing_ids_relevantes.add(g.id_ingrediente_id)

    ingredientes_map = {
        ing.id_ingrediente: ing
        for ing in Ingrediente.objects.filter(id_ingrediente__in=ing_ids_relevantes).select_related(
            'id_categoria_inventario', 'id_tipo_mercado', 'id_unidad_medida'
        )
    }
    # Incluir insumos de aseo registrados en catálogo si existieran para que la tabla Aseo nunca pierda catálogo real
    for ing in Ingrediente.objects.select_related(
        'id_categoria_inventario', 'id_tipo_mercado', 'id_unidad_medida'
    ).all():
        if _clasificar_grupo_ingrediente(ing) == 'ASEO':
            ingredientes_map[ing.id_ingrediente] = ing
            ing_ids_relevantes.add(ing.id_ingrediente)

    def _unidad_objetivo_para_ingrediente(ing_id: int) -> UnidadMedida | None:
        ing = ingredientes_map.get(ing_id)
        prog_u_txt = programado_por_ing[ing_id]['unidad_abreviatura'] if ing_id in programado_por_ing else ''
        if prog_u_txt and _normalizar_texto(prog_u_txt) in unidades_by_key:
            return unidades_by_key[_normalizar_texto(prog_u_txt)]
        if ing and ing.id_unidad_medida_id:
            return ing.id_unidad_medida
        inv_u_id = inventario_unidad_map.get(ing_id)
        if inv_u_id and inv_u_id in unidades_by_id:
            return unidades_by_id[inv_u_id]
        return unidad_kg or unidad_g

    # Indexar gramajes reales por ingrediente y nivel antes de armar Remisión y Minuta
    gramajes_ing_nivel = defaultdict(lambda: defaultdict(list))
    for g in gramajes_activos:
        if not g.id_ingrediente_id or not g.id_grado_id:
            continue
        if grados_atendidos_ids and g.id_grado_id not in grados_atendidos_ids:
            continue
        ing = g.id_ingrediente
        niv_key = grado_nivel_map.get(g.id_grado_id) or _clasificar_nivel_cupos(
            g.id_grado.nivel_educativo, g.id_grado.nombre_grado
        )
        u_g = g.id_unidad_medida
        cant_base = Decimal(str(g.cantidad_gramaje or 0))
        if u_g and unidad_g and getattr(u_g, 'tipo_magnitud', '') == 'MASA':
            cant_base = _convertir_a_unidad(cant_base, u_g, unidad_g, ing)
            unidad_min = 'g'
        else:
            unidad_min = (u_g.abreviatura if u_g and u_g.abreviatura else 'g')
        gramajes_ing_nivel[g.id_ingrediente_id][niv_key].append({
            'id_grado': g.id_grado_id,
            'cant': cant_base,
            'unidad': unidad_min,
        })

    def _gramajes_resumen_ingrediente(ing_id: int) -> dict:
        niv_dict = gramajes_ing_nivel.get(ing_id) or {}
        def _prom(nk: str) -> float:
            lst = niv_dict.get(nk) or []
            if not lst:
                return 0.0
            return float(round(sum(x['cant'] for x in lst) / Decimal(len(lst)), 2))
        return {
            'preescolar': _prom('preescolar'),
            'primaria13': _prom('primaria13'),
            'primaria45': _prom('primaria45'),
            'secundaria': _prom('secundaria'),
            'media': _prom('media'),
        }

    # Agregar entregas reales por ingrediente y semana
    entregas_agg = defaultdict(lambda: {
        'despachado': Decimal('0'),
        'recibido': Decimal('0'),
        'rechazado': Decimal('0'),
        'desp_e': [Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0')],
        'rec_e': [Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0')],
        'fecha_ultima': '',
        'fecha_vencimiento': '',
        'observaciones': [],
        'tiene_transito': False,
        'tiene_novedad': False,
    })

    for ent in entregas_lista:
        ing_id = ent.id_ingrediente
        ing_obj = ingredientes_map.get(ing_id)
        u_dest = _unidad_objetivo_para_ingrediente(ing_id)
        u_orig = unidades_by_key.get(_normalizar_texto(ent.unidad)) if ent.unidad else u_dest

        cant_desp = _convertir_a_unidad(Decimal(str(ent.cantidad or 0)), u_orig, u_dest, ing_obj)
        estado_u = str(ent.estado or '').upper()
        if estado_u in {'RECIBIDA', 'CON_NOVEDAD'}:
            cant_rec_raw = ent.cantidad_recibida if ent.cantidad_recibida is not None else ent.cantidad
            cant_rec = _convertir_a_unidad(Decimal(str(cant_rec_raw or 0)), u_orig, u_dest, ing_obj)
        else:
            cant_rec = Decimal('0')
        cant_rech = _convertir_a_unidad(Decimal(str(ent.cantidad_rechazada or 0)), u_orig, u_dest, ing_obj)

        agg = entregas_agg[ing_id]
        agg['despachado'] += cant_desp
        agg['recibido'] += cant_rec
        agg['rechazado'] += cant_rech

        fecha_ref_sem = _fecha_local(ent.fecha_recepcion) or ent.fecha_entrega
        idx_sem = min(3, max(0, (fecha_ref_sem - fecha_inicio).days // 7))
        agg['desp_e'][idx_sem] += cant_desp
        agg['rec_e'][idx_sem] += cant_rec

        f_str = ent.fecha_entrega.isoformat() if ent.fecha_entrega else ''
        if f_str and f_str > agg['fecha_ultima']:
            agg['fecha_ultima'] = f_str
        fv_str = ent.fecha_vencimiento.isoformat() if ent.fecha_vencimiento else ''
        if fv_str and (not agg['fecha_vencimiento'] or fv_str < agg['fecha_vencimiento']):
            agg['fecha_vencimiento'] = fv_str

        if estado_u == 'EN_TRANSITO':
            agg['tiene_transito'] = True
        if estado_u in {'CON_NOVEDAD', 'RECHAZADA'}:
            agg['tiene_novedad'] = True

        obs_txt = (ent.motivo_rechazo or ent.observaciones or '').strip()
        if obs_txt and obs_txt not in agg['observaciones']:
            agg['observaciones'].append(obs_txt)

    # ---------- CONSTRUIR REMISIÓN CON CATÁLOGO BASE + DATOS REALES FUSIONADOS ----------
    ing_ids_ordenados = sorted(
        ing_ids_relevantes,
        key=lambda i: (ingredientes_map[i].nombre_ingrediente or '') if i in ingredientes_map else '',
    )
    claves_por_ing = {
        ing_id: _claves_alimento(ingredientes_map[ing_id].nombre_ingrediente or '')
        for ing_id in ing_ids_ordenados
        if ing_id in ingredientes_map
    }
    grupo_por_ing = {
        ing_id: _clasificar_grupo_ingrediente(ingredientes_map[ing_id])
        for ing_id in ing_ids_ordenados
        if ing_id in ingredientes_map
    }

    def _datos_reales_remision(ing_id: int) -> dict:
        ing = ingredientes_map[ing_id]
        u_dest = _unidad_objetivo_para_ingrediente(ing_id)
        unidad_abrev = (u_dest.abreviatura if u_dest and u_dest.abreviatura else (u_dest.nombre if u_dest else 'Und'))

        prog_info = programado_por_ing.get(ing_id)
        prog_total = prog_info['cantidad_periodo'] if prog_info else Decimal('0')
        prog_sem = prog_info['cantidad_semanal'] if prog_info else Decimal('0')

        agg = entregas_agg.get(ing_id)
        despachado = agg['despachado'] if agg else Decimal('0')
        recibido = agg['recibido'] if agg else Decimal('0')
        rechazado = agg['rechazado'] if agg else Decimal('0')

        obs_partes = list(agg['observaciones']) if agg else []
        if agg and agg['tiene_transito'] and recibido == 0:
            obs_partes.append('En tránsito')
        if rechazado > 0:
            obs_partes.append(f"Rechazado: {float(round(rechazado, 2))}")
        obs_final = ' | '.join(obs_partes)

        a_entregar = float(round(prog_total if prog_total > 0 else despachado, 2))
        recibido_num = float(round(recibido, 2))
        despachado_num = float(round(despachado, 2))
        desp_s = [float(round(x, 2)) for x in (agg['desp_e'] if agg else [Decimal('0')] * 4)]
        rec_s = [float(round(x, 2)) for x in (agg['rec_e'] if agg else [Decimal('0')] * 4)]

        asig_info = asig_inst_map.get(ing_id)
        asig_inst_cant = 0.0
        asig_pend_cant = 0.0
        if asig_info:
            u_asig = unidades_by_id.get(asig_info.get('id_unidad_medida'))
            asig_inst_cant = float(round(
                _convertir_a_unidad(Decimal(str(asig_info.get('cantidad_asignada') or 0)), u_asig, u_dest, ing),
                2,
            ))
            asig_pend_cant = float(round(
                _convertir_a_unidad(Decimal(str(asig_info.get('cantidad_pendiente') or 0)), u_asig, u_dest, ing),
                2,
            ))

        return {
            'ing': ing,
            'grupo': grupo_por_ing.get(ing_id, 'NO_PERECEDERO'),
            'unidad': unidad_abrev,
            'frecuencia': (prog_info['frecuencia'] if prog_info and prog_info['frecuencia'] else ''),
            'prog_total': float(round(prog_total, 2)),
            'prog_sem': float(round(prog_sem, 2)),
            'despachado': despachado_num,
            'aEntregar': a_entregar,
            'recibido': recibido_num,
            'desp_s': desp_s,
            'rec_s': rec_s,
            'fechaEntrega': agg['fecha_ultima'] if agg else '',
            'fechaVencimiento': agg['fecha_vencimiento'] if agg else '',
            'observaciones': obs_final,
            'gramajes': _gramajes_resumen_ingrediente(ing_id),
            'tieneAsignacion': bool(asig_info),
            'asignadoInstitucion': asig_inst_cant,
            'pendienteAsignacion': asig_pend_cant,
        }

    no_perecederos = []
    perecederos = []
    aseo = []
    remision_emparejados = set()

    # 1. No Perecederos por defecto + cruce automático con DB real
    cand_np = [i for i in ing_ids_ordenados if grupo_por_ing.get(i) == 'NO_PERECEDERO']
    cand_no_aseo = [i for i in ing_ids_ordenados if grupo_por_ing.get(i) != 'ASEO']
    for base in NO_PERECEDEROS_BASE:
        match_id = _buscar_ingrediente_coincidente(
            base['alimento'], cand_np, ingredientes_map, claves_por_ing, remision_emparejados
        ) or _buscar_ingrediente_coincidente(
            base['alimento'], cand_no_aseo, ingredientes_map, claves_por_ing, remision_emparejados
        )
        if match_id:
            remision_emparejados.add(match_id)
            dr = _datos_reales_remision(match_id)
            tiene_cant_real = dr['aEntregar'] > 0 or dr['recibido'] > 0
            a_ent = dr['aEntregar'] if dr['aEntregar'] > 0 else float(base['baseMes'])
            no_perecederos.append({
                'id_ingrediente': match_id,
                'producto': base['alimento'],
                'unidad': (dr['unidad'] or base['unidad']) if tiene_cant_real else base['unidad'],
                'frecuencia': dr['frecuencia'] or 'MENSUAL',
                'gramajes': _fusionar_gramajes(base['gramajes'], dr['gramajes']),
                'programado': dr['prog_total'],
                'despachado': dr['despachado'],
                'aEntregar': a_ent,
                'fechaVencimiento': dr['fechaVencimiento'],
                'fechaEntrega': dr['fechaEntrega'],
                'recibido': dr['recibido'],
                'observaciones': dr['observaciones'],
                'tieneAsignacion': dr['tieneAsignacion'],
                'asignadoInstitucion': dr['asignadoInstitucion'],
                'pendienteAsignacion': dr['pendienteAsignacion'],
                'tieneActividadSede': bool(tiene_cant_real or dr['tieneAsignacion'] or dr['despachado'] > 0),
            })
        else:
            no_perecederos.append({
                'id_ingrediente': None,
                'producto': base['alimento'],
                'unidad': base['unidad'],
                'frecuencia': 'MENSUAL',
                'gramajes': dict(base['gramajes']),
                'programado': 0.0,
                'despachado': 0.0,
                'aEntregar': float(base['baseMes']),
                'fechaVencimiento': '',
                'fechaEntrega': '',
                'recibido': 0.0,
                'observaciones': '',
            })

    # 2. Perecederos por defecto + cruce automático con DB real
    cand_per = [i for i in ing_ids_ordenados if grupo_por_ing.get(i) == 'PERECEDERO']
    for base in PERECEDEROS_BASE:
        match_id = _buscar_ingrediente_coincidente(
            base['alimento'], cand_per, ingredientes_map, claves_por_ing, remision_emparejados
        ) or _buscar_ingrediente_coincidente(
            base['alimento'], cand_no_aseo, ingredientes_map, claves_por_ing, remision_emparejados
        )
        if match_id:
            remision_emparejados.add(match_id)
            dr = _datos_reales_remision(match_id)
            tiene_cant_real = any(x > 0 for x in dr['desp_s']) or dr['prog_sem'] > 0 or dr['recibido'] > 0
            semanas_detalle = [
                {
                    'aEntregar': (
                        dr['desp_s'][w] if dr['desp_s'][w] > 0
                        else (dr['prog_sem'] if dr['prog_sem'] > 0 else float(base['baseSemanal'][w]))
                    ),
                    'recibida': dr['rec_s'][w],
                }
                for w in range(4)
            ]
            perecederos.append({
                'id_ingrediente': match_id,
                'producto': base['alimento'],
                'unidad': (dr['unidad'] or base['unidad']) if tiene_cant_real else base['unidad'],
                'frecuencia': 'SEMANAL',
                'gramajes': _fusionar_gramajes(base['gramajes'], dr['gramajes']),
                'programadoSemanal': dr['prog_sem'],
                'programadoTotal': dr['prog_total'],
                'despachado': dr['despachado'],
                'entregas': semanas_detalle,
                'totalEntregado': round(sum(s['aEntregar'] for s in semanas_detalle), 2),
                'e1': semanas_detalle[0]['aEntregar'],
                'e2': semanas_detalle[1]['aEntregar'],
                'e3': semanas_detalle[2]['aEntregar'],
                'e4': semanas_detalle[3]['aEntregar'],
                'recibido': dr['recibido'],
                'fechaEntrega': dr['fechaEntrega'],
                'fechaVencimiento': dr['fechaVencimiento'],
                'observaciones': dr['observaciones'],
                'tieneAsignacion': dr['tieneAsignacion'],
                'asignadoInstitucion': dr['asignadoInstitucion'],
                'pendienteAsignacion': dr['pendienteAsignacion'],
                'tieneActividadSede': bool(tiene_cant_real or dr['tieneAsignacion'] or dr['despachado'] > 0),
            })
        else:
            semanas_detalle = [
                {'aEntregar': float(base['baseSemanal'][w]), 'recibida': 0.0}
                for w in range(4)
            ]
            perecederos.append({
                'id_ingrediente': None,
                'producto': base['alimento'],
                'unidad': base['unidad'],
                'frecuencia': 'SEMANAL',
                'gramajes': dict(base['gramajes']),
                'programadoSemanal': 0.0,
                'programadoTotal': 0.0,
                'despachado': 0.0,
                'entregas': semanas_detalle,
                'totalEntregado': round(sum(s['aEntregar'] for s in semanas_detalle), 2),
                'e1': semanas_detalle[0]['aEntregar'],
                'e2': semanas_detalle[1]['aEntregar'],
                'e3': semanas_detalle[2]['aEntregar'],
                'e4': semanas_detalle[3]['aEntregar'],
                'recibido': 0.0,
                'fechaEntrega': '',
                'fechaVencimiento': '',
                'observaciones': '',
            })

    # 3. Aseo por defecto + cruce automático con DB real
    cand_aseo = [i for i in ing_ids_ordenados if grupo_por_ing.get(i) == 'ASEO']
    for base in ASEO_BASE:
        match_id = _buscar_ingrediente_coincidente(
            base['item'], cand_aseo, ingredientes_map, claves_por_ing, remision_emparejados
        )
        if match_id:
            remision_emparejados.add(match_id)
            dr = _datos_reales_remision(match_id)
            a_ent = dr['aEntregar'] if dr['aEntregar'] > 0 else float(base['baseMes'])
            aseo.append({
                'id_ingrediente': match_id,
                'producto': base['item'],
                'unidad': dr['unidad'] or base['unidad'],
                'frecuencia': dr['frecuencia'] or 'MENSUAL',
                'programado': dr['prog_total'],
                'despachado': dr['despachado'],
                'aEntregar': a_ent,
                'fechaEntrega': dr['fechaEntrega'],
                'fechaVencimiento': dr['fechaVencimiento'],
                'recibido': dr['recibido'],
                'observaciones': dr['observaciones'],
                'tieneAsignacion': dr['tieneAsignacion'],
                'asignadoInstitucion': dr['asignadoInstitucion'],
                'pendienteAsignacion': dr['pendienteAsignacion'],
                'tieneActividadSede': bool(
                    dr['aEntregar'] > 0 or dr['recibido'] > 0 or dr['tieneAsignacion'] or dr['despachado'] > 0
                ),
            })
        else:
            aseo.append({
                'id_ingrediente': None,
                'producto': base['item'],
                'unidad': base['unidad'],
                'frecuencia': 'MENSUAL',
                'programado': 0.0,
                'despachado': 0.0,
                'aEntregar': float(base['baseMes']),
                'fechaEntrega': '',
                'fechaVencimiento': '',
                'recibido': 0.0,
                'observaciones': '',
                'tieneAsignacion': False,
                'asignadoInstitucion': 0.0,
                'pendienteAsignacion': 0.0,
                'tieneActividadSede': False,
            })

    # 4. Agregar automáticamente cualquier otro ingrediente real de DB no presente en el catálogo base
    for ing_id in ing_ids_ordenados:
        if ing_id in remision_emparejados or ing_id not in ingredientes_map:
            continue
        dr = _datos_reales_remision(ing_id)
        grupo = dr['grupo']
        nombre_ing = dr['ing'].nombre_ingrediente or f'Producto #{ing_id}'
        actividad_real = bool(
            dr['aEntregar'] > 0
            or dr['recibido'] > 0
            or dr['tieneAsignacion']
            or dr['despachado'] > 0
            or dr['prog_total'] > 0
        )
        asig_extra = {
            'tieneAsignacion': dr['tieneAsignacion'],
            'asignadoInstitucion': dr['asignadoInstitucion'],
            'pendienteAsignacion': dr['pendienteAsignacion'],
            'tieneActividadSede': actividad_real,
        }
        if grupo == 'ASEO':
            aseo.append({
                'id_ingrediente': ing_id,
                'producto': nombre_ing,
                'unidad': dr['unidad'],
                'frecuencia': dr['frecuencia'] or 'MENSUAL',
                'programado': dr['prog_total'],
                'despachado': dr['despachado'],
                'aEntregar': dr['aEntregar'],
                'fechaEntrega': dr['fechaEntrega'],
                'fechaVencimiento': dr['fechaVencimiento'],
                'recibido': dr['recibido'],
                'observaciones': dr['observaciones'],
                **asig_extra,
            })
        elif grupo == 'PERECEDERO':
            semanas_detalle = [
                {
                    'aEntregar': dr['desp_s'][w] if dr['desp_s'][w] > 0 else dr['prog_sem'],
                    'recibida': dr['rec_s'][w],
                }
                for w in range(4)
            ]
            perecederos.append({
                'id_ingrediente': ing_id,
                'producto': nombre_ing,
                'unidad': dr['unidad'],
                'frecuencia': 'SEMANAL',
                'gramajes': dr['gramajes'],
                'programadoSemanal': dr['prog_sem'],
                'programadoTotal': dr['prog_total'],
                'despachado': dr['despachado'],
                'entregas': semanas_detalle,
                'totalEntregado': round(sum(s['aEntregar'] for s in semanas_detalle), 2),
                'e1': semanas_detalle[0]['aEntregar'],
                'e2': semanas_detalle[1]['aEntregar'],
                'e3': semanas_detalle[2]['aEntregar'],
                'e4': semanas_detalle[3]['aEntregar'],
                'recibido': dr['recibido'],
                'fechaEntrega': dr['fechaEntrega'],
                'fechaVencimiento': dr['fechaVencimiento'],
                'observaciones': dr['observaciones'],
                **asig_extra,
            })
        else:
            no_perecederos.append({
                'id_ingrediente': ing_id,
                'producto': nombre_ing,
                'unidad': dr['unidad'],
                'frecuencia': dr['frecuencia'] or 'MENSUAL',
                'gramajes': dr['gramajes'],
                'programado': dr['prog_total'],
                'despachado': dr['despachado'],
                'aEntregar': dr['aEntregar'],
                'fechaVencimiento': dr['fechaVencimiento'],
                'fechaEntrega': dr['fechaEntrega'],
                'recibido': dr['recibido'],
                'observaciones': dr['observaciones'],
                **asig_extra,
            })

    # ---------- CONSTRUIR KÁRDEX REAL ----------
    entradas_manual_map = defaultdict(Decimal)
    for ent_inv in entradas_lista:
        ing_id = ent_inv.id_ingrediente_id
        ing_obj = ingredientes_map.get(ing_id) or ent_inv.id_ingrediente
        u_dest = _unidad_objetivo_para_ingrediente(ing_id)
        cant = _convertir_a_unidad(
            Decimal(str(ent_inv.cantidad or 0)), ent_inv.id_unidad_medida, u_dest, ing_obj
        )
        entradas_manual_map[ing_id] += cant

    salidas_por_ing_fecha = defaultdict(lambda: defaultdict(Decimal))
    for sal in salidas_lista:
        ing_id = sal.id_ingrediente_id
        ing_obj = ingredientes_map.get(ing_id) or sal.id_ingrediente
        u_dest = _unidad_objetivo_para_ingrediente(ing_id)
        cant = _convertir_a_unidad(
            Decimal(str(sal.cantidad or 0)), sal.id_unidad_medida, u_dest, ing_obj
        )
        f_sal = _fecha_local(sal.fecha)
        if f_sal:
            salidas_por_ing_fecha[ing_id][f_sal] += cant

    alimentos_kardex = []
    kardex_emparejados = set()

    def _construir_fila_kardex_ing(
        ing_id: int,
        nombre_visible: str | None = None,
        menu_visible: str = 'Minuta SIRAE',
        entrada_default: float | None = None,
        unidad_default: str | None = None,
    ) -> dict:
        ing = ingredientes_map[ing_id]
        u_dest = _unidad_objetivo_para_ingrediente(ing_id)

        rec_entregas = entregas_agg[ing_id]['recibido'] if ing_id in entregas_agg else Decimal('0')
        ent_manual = entradas_manual_map.get(ing_id, Decimal('0'))
        entrada_real = rec_entregas + ent_manual
        entrada_final = (
            float(round(entrada_real, 2))
            if entrada_real > 0
            else (float(entrada_default) if entrada_default is not None else 0.0)
        )

        gastos_dias = [
            float(round(salidas_por_ing_fecha[ing_id].get(d, Decimal('0')), 2))
            for d in dias_habiles
        ]
        total_gasto = float(round(sum(salidas_por_ing_fecha[ing_id].values()), 2))
        tiene_mov = entrada_real > 0 or total_gasto > 0 or entrada_default is None
        unidad_abrev = (
            (u_dest.abreviatura if u_dest and u_dest.abreviatura else (u_dest.nombre if u_dest else 'Und'))
            if tiene_mov
            else (unidad_default or 'Und')
        )
        saldo_periodo = float(round(entrada_final - total_gasto, 2))

        inv_u_id = inventario_unidad_map.get(ing_id)
        inv_cant_raw = inventario_sede_map.get(ing_id)
        if inv_cant_raw is not None:
            inv_cant_conv = _convertir_a_unidad(
                inv_cant_raw, unidades_by_id.get(inv_u_id), u_dest, ing
            )
            stock_actual_bodega = float(round(inv_cant_conv, 2))
        else:
            stock_actual_bodega = None

        asig_info = asig_inst_map.get(ing_id)
        asig_inst_cant = 0.0
        if asig_info:
            u_asig = unidades_by_id.get(asig_info.get('id_unidad_medida'))
            asig_inst_cant = float(round(
                _convertir_a_unidad(Decimal(str(asig_info.get('cantidad_asignada') or 0)), u_asig, u_dest, ing),
                2,
            ))

        return {
            'id_ingrediente': ing_id,
            'nombre': nombre_visible or ing.nombre_ingrediente or f'Alimento #{ing_id}',
            'menu': menu_visible,
            'unidad': unidad_abrev,
            'fechaEntrada': (entregas_agg[ing_id]['fecha_ultima'] if ing_id in entregas_agg else '') or fecha_inicio.isoformat(),
            'entrada': entrada_final,
            'entradaEntregas': float(round(rec_entregas, 2)),
            'entradaInventarioManual': float(round(ent_manual, 2)),
            'gastos': gastos_dias,
            'totalGasto': round(total_gasto, 2),
            'saldo': stock_actual_bodega if stock_actual_bodega is not None else max(0.0, saldo_periodo),
            'saldoPeriodo': saldo_periodo,
            'stockActualInventario': stock_actual_bodega,
            'tieneAsignacion': bool(asig_info),
            'asignadoInstitucion': asig_inst_cant,
            'tieneActividadSede': bool(
                asig_info
                or entrada_real > 0
                or total_gasto > 0
                or (stock_actual_bodega or 0) > 0
                or ing_id in programado_por_ing
            ),
        }

    # 1. Ítems base oficiales del Kárdex + cruce automático con entregas/entradas/salidas reales
    for base in KARDEX_ALIMENTOS_BASE:
        match_id = _buscar_ingrediente_coincidente(
            base['alimento'], cand_no_aseo, ingredientes_map, claves_por_ing, kardex_emparejados
        )
        if match_id:
            kardex_emparejados.add(match_id)
            alimentos_kardex.append(
                _construir_fila_kardex_ing(
                    match_id,
                    nombre_visible=base['alimento'],
                    menu_visible=base['menu'],
                    entrada_default=base['entrada'],
                    unidad_default=base['unidad'],
                )
            )
        else:
            entrada_base = float(base['entrada'])
            alimentos_kardex.append({
                'id_ingrediente': None,
                'nombre': base['alimento'],
                'menu': base['menu'],
                'unidad': base['unidad'],
                'fechaEntrada': fecha_inicio.isoformat(),
                'entrada': entrada_base,
                'entradaEntregas': 0.0,
                'entradaInventarioManual': 0.0,
                'gastos': [0.0 for _ in dias_habiles],
                'totalGasto': 0.0,
                'saldo': entrada_base,
                'saldoPeriodo': entrada_base,
                'stockActualInventario': None,
            })

    # 2. Agregar automáticamente cualquier alimento real cargado/movido en DB no incluido arriba
    for ing_id in ing_ids_ordenados:
        if ing_id in kardex_emparejados or ing_id not in ingredientes_map:
            continue
        if grupo_por_ing.get(ing_id) == 'ASEO':
            if ing_id not in entradas_manual_map and ing_id not in salidas_por_ing_fecha and ing_id not in entregas_agg:
                continue
        kardex_emparejados.add(ing_id)
        alimentos_kardex.append(_construir_fila_kardex_ing(ing_id))

    # ---------- CONSTRUIR MINUTA PATRÓN: CATÁLOGO BASE + GRAMAJES/CUPOS REALES ----------
    minuta_patron = []
    minuta_emparejados = set()

    def _grupo_minuta_perecedero(alimento_nombre: str) -> str:
        up = alimento_nombre.upper()
        if 'FRUTA' in up:
            return 'FRUTAS'
        if 'VERDURA' in up or 'PAPA' in up or 'AJO' in up or 'HABICHUELA' in up:
            return 'VERDURAS Y TUBÉRCULOS'
        if 'HUEVOS' in up:
            return 'LÁCTEOS Y HUEVOS'
        return 'CÁRNICOS Y PROTEÍNAS'

    def _append_item_minuta(
        ing_id: int | None,
        componente: str,
        alimento: str,
        unidad_muestra: str,
        gramajes_niv: dict,
    ):
        gp = Decimal(str(gramajes_niv.get('preescolar', 0)))
        gp13 = Decimal(str(gramajes_niv.get('primaria13', 0)))
        gp45 = Decimal(str(gramajes_niv.get('primaria45', 0)))
        gs = Decimal(str(gramajes_niv.get('secundaria', 0)))
        gm = Decimal(str(gramajes_niv.get('media', 0)))

        sub_p = gp * Decimal(cupos_nivel['preescolar']) * Decimal(dias_periodo)
        sub_p13 = gp13 * Decimal(cupos_nivel['primaria13']) * Decimal(dias_periodo)
        sub_p45 = gp45 * Decimal(cupos_nivel['primaria45']) * Decimal(dias_periodo)
        sub_s = gs * Decimal(cupos_nivel['secundaria']) * Decimal(dias_periodo)
        sub_m = gm * Decimal(cupos_nivel['media']) * Decimal(dias_periodo)
        total_gramos_periodo = sub_p + sub_p13 + sub_p45 + sub_s + sub_m
        total_kg_litros = total_gramos_periodo / Decimal('1000')

        minuta_patron.append({
            'id_ingrediente': ing_id,
            'componente': componente,
            'alimento': alimento,
            'unidad': unidad_muestra,
            'gramajePreescolar': float(round(gp, 2)),
            'gramajePrimaria13': float(round(gp13, 2)),
            'gramajePrimaria45': float(round(gp45, 2)),
            'gramajeSecundaria': float(round(gs, 2)),
            'gramajeMedia': float(round(gm, 2)),
            'subtotalPreescolar': float(round(sub_p, 1)),
            'subtotalPrimaria13': float(round(sub_p13, 1)),
            'subtotalPrimaria45': float(round(sub_p45, 1)),
            'subtotalSecundaria': float(round(sub_s, 1)),
            'subtotalMedia': float(round(sub_m, 1)),
            'totalGramosPeriodo': float(round(total_gramos_periodo, 1)),
            'totalKgLitros': float(round(total_kg_litros, 2)),
        })

    for base in NO_PERECEDEROS_BASE:
        match_id = _buscar_ingrediente_coincidente(
            base['alimento'], cand_no_aseo, ingredientes_map, claves_por_ing, minuta_emparejados
        )
        if match_id:
            minuta_emparejados.add(match_id)
        gramajes_fin = _fusionar_gramajes(base['gramajes'], _gramajes_resumen_ingrediente(match_id) if match_id else None)
        _append_item_minuta(match_id, 'NO PERECEDEROS', base['alimento'], base['unidad'], gramajes_fin)

    for base in PERECEDEROS_BASE:
        match_id = _buscar_ingrediente_coincidente(
            base['alimento'], cand_no_aseo, ingredientes_map, claves_por_ing, minuta_emparejados
        )
        if match_id:
            minuta_emparejados.add(match_id)
        gramajes_fin = _fusionar_gramajes(base['gramajes'], _gramajes_resumen_ingrediente(match_id) if match_id else None)
        _append_item_minuta(
            match_id,
            _grupo_minuta_perecedero(base['alimento']),
            base['alimento'],
            base['unidad'],
            gramajes_fin,
        )

    for ing_id, niveles_dict in sorted(
        gramajes_ing_nivel.items(),
        key=lambda kv: (ingredientes_map[kv[0]].nombre_ingrediente or '') if kv[0] in ingredientes_map else '',
    ):
        if ing_id in minuta_emparejados:
            continue
        ing = ingredientes_map.get(ing_id)
        if not ing:
            continue
        unidad_muestra = 'g'
        for lst in niveles_dict.values():
            if lst:
                unidad_muestra = lst[0]['unidad']
                break
        cat_nombre = (
            ing.id_categoria_inventario.nombre_categoria
            if ing.id_categoria_inventario and ing.id_categoria_inventario.nombre_categoria
            else (_clasificar_grupo_ingrediente(ing).replace('_', ' ').title())
        )
        _append_item_minuta(
            ing_id,
            cat_nombre,
            ing.nombre_ingrediente or f'Alimento #{ing_id}',
            unidad_muestra,
            _gramajes_resumen_ingrediente(ing_id),
        )

    # ---------- METADATOS FINALES ----------
    codigos_dane = ', '.join(
        sorted({str(s.codigo_dane).strip() for s in sedes_objetivo if s.codigo_dane})
    )
    nombre_sede_enc = (
        sede_sel.nombre_sede
        if sede_sel
        else (
            sedes_objetivo[0].nombre_sede
            if len(sedes_objetivo) == 1
            else f"Todas las sedes ({len(sedes_objetivo)})"
        )
    )
    telefono_enc = (
        (sede_sel.telefono if sede_sel and sede_sel.telefono else '')
        or (sedes_objetivo[0].telefono if len(sedes_objetivo) == 1 and sedes_objetivo[0].telefono else '')
        or institucion.telefono
        or ''
    )
    direccion_enc = (
        (sede_sel.direccion if sede_sel and sede_sel.direccion else '')
        or (sedes_objetivo[0].direccion if len(sedes_objetivo) == 1 and sedes_objetivo[0].direccion else '')
        or (institucion.correo_contacto or '')
    )

    return {
        'sin_alcance': False,
        'institucion': {
            'id_institucion': institucion.id_institucion,
            'nombre_institucion': institucion.nombre_institucion,
            'nit': institucion.nit,
            'telefono': institucion.telefono or '',
            'correo_contacto': institucion.correo_contacto or '',
            'representante_legal': institucion.representante_legal or '',
        },
        'sede': (
            {
                'id_sede': sede_sel.id_sede,
                'nombre_sede': sede_sel.nombre_sede,
                'codigo_dane': sede_sel.codigo_dane or '',
                'direccion': sede_sel.direccion or '',
                'telefono': sede_sel.telefono or '',
            }
            if sede_sel
            else None
        ),
        'sedes_disponibles': [
            {
                'id_sede': s.id_sede,
                'nombre_sede': s.nombre_sede,
                'codigo_dane': s.codigo_dane or '',
                'direccion': s.direccion or '',
                'telefono': s.telefono or '',
                'id_institucion': s.id_institucion_id,
            }
            for s in sedes_inst
        ],
        'contrato': (
            {
                'id_contrato': contrato_principal.id_contrato,
                'numero_cor': contrato_principal.numero_cor or '',
                'operador': contrato_principal.institucion or '',
                'zona': contrato_principal.zona or '',
                'fecha_inicio': contrato_principal.fecha_inicio.isoformat() if contrato_principal.fecha_inicio else '',
                'fecha_fin': contrato_principal.fecha_fin.isoformat() if contrato_principal.fecha_fin else '',
                'estado': contrato_principal.estado or '',
                'cupos': contrato_principal.cupos,
                'periodicidad_perecederos': contrato_principal.periodicidad_perecederos,
                'dias_cobertura_perecederos': contrato_principal.dias_cobertura_perecederos,
                'periodicidad_no_perecederos': contrato_principal.periodicidad_no_perecederos,
                'dias_cobertura_no_perecederos': contrato_principal.dias_cobertura_no_perecederos,
            }
            if contrato_principal
            else None
        ),
        'encabezado': {
            'departamento': '',
            'municipio': (contrato_principal.zona if contrato_principal and contrato_principal.zona else ''),
            'entidad_territorial': 'Programa de Alimentación Escolar - SIRAE',
            'nombre_institucion': institucion.nombre_institucion,
            'nombre_sede': nombre_sede_enc,
            'codigo_dane': codigos_dane,
            'operador': (contrato_principal.institucion if contrato_principal and contrato_principal.institucion else ''),
            'numero_contrato': (contrato_principal.numero_cor if contrato_principal and contrato_principal.numero_cor else ''),
            'telefono': telefono_enc,
            'direccion': direccion_enc,
            'fecha_inicio': fecha_inicio.isoformat(),
            'fecha_fin': fecha_fin.isoformat(),
            'dias_atender': dias_periodo,
        },
        'cupos': {
            'total': total_cupos,
            'preescolar': cupos_nivel['preescolar'],
            'primaria13': cupos_nivel['primaria13'],
            'primaria45': cupos_nivel['primaria45'],
            'secundaria': cupos_nivel['secundaria'],
            'media': cupos_nivel['media'],
            'otro': cupos_nivel['otro'],
            'origen': origen_cupos,
            'detalle_grados': detalle_grados,
        },
        'responsables': {
            'manipuladora_jefe': jefas_manipuladoras[0] if jefas_manipuladoras else None,
            'manipuladora': manipuladoras[0] if manipuladoras else None,
            'manipuladoras': manipuladoras,
            'jefas_manipuladoras': jefas_manipuladoras,
            'administrador': administradores[0] if administradores else None,
            'administradores': administradores,
            'supervisor': supervisores[0] if supervisores else None,
            'supervisores': supervisores,
            'receptor_entrega': receptor_entrega,
        },
        'remision': {
            'no_perecederos': no_perecederos,
            'perecederos': perecederos,
            'aseo': aseo,
        },
        'kardex': {
            'dias': dias_iso,
            'raciones_dia': raciones_dia,
            'total_atendido': sum(asistencia_por_fecha.values()),
            'alimentos': alimentos_kardex,
        },
        'minuta_patron': minuta_patron,
        'resumen_actividad': {
            'entregas_count': len(entregas_lista),
            'salidas_count': len(salidas_lista),
            'entradas_count': len(entradas_lista),
            'asistencias_count': len(asistencia_lista),
        },
        'tiene_asignacion_institucion': bool(asig_resumen.get('tiene_asignaciones')),
        'asignaciones_institucion': asig_resumen.get('items', []),
        'alcance': describir_alcance_usuario(usuario),
    }
