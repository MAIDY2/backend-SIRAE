import json
import logging
import os
import random
import unicodedata
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps_sirae.detalle_plato.models import DetallePlato
from apps_sirae.gramage.models import Gramage
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.inventario.models import Inventario
from apps_sirae.menus.models import Menu
from apps_sirae.platos.models import Plato
from apps_sirae.receta_componente.models import RecetaComponente
from apps_sirae.salidas_inventario.models import SalidaInventario
from apps_sirae.secciones_menu.models import SeccionMenu
from apps_sirae.sedes.models import Sede
from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.ia_sugerencias.mongodb import (
    guardar_historial_sugerencia,
    obtener_historial_sugerencias,
    guardar_auditoria_consumo,
    verificar_conexion_mongo,
    sincronizar_catalogo_recetas,
)

logger = logging.getLogger(__name__)

# ==============================================================================
# CATÁLOGO DE LOS 20 MENÚS OFICIALES DEL CICLO PAE (BASE DE CONOCIMIENTO)
# ==============================================================================
CATALOGO_20_MENUS_PAE = [
    {
        "numeroMenu": 1,
        "semana": 1,
        "seccion": "Desayuno",
        "nombre_plato": "Pericos con arroz",
        "componentes": {
            "bebida_leche": "Refresco de avena",
            "proteico": "Huevos pericos",
            "cereal": "Arroz blanco",
            "fruta": "—",
            "agua": "Agua potable",
        },
        "ingredientes": ["Avena", "Leche líquida", "Azúcar", "Huevos", "Tomate", "Cebolla", "Arroz", "Ajo", "Aceite vegetal", "Sal"],
        "pasos": [
            "Preparar el refresco de avena con leche líquida y azúcar.",
            "Elaborar los huevos pericos bien cocidos con tomate y cebolla.",
            "Cocinar el arroz blanco con ajo y sal, servir caliente.",
        ],
    },
    {
        "numeroMenu": 2,
        "semana": 1,
        "seccion": "Almuerzo",
        "nombre_plato": "Pollo en salsa blanca con pasta",
        "componentes": {
            "bebida_leche": "Jugo de fruta en leche",
            "proteico": "Pollo en salsa blanca",
            "cereal": "Pasta",
            "fruta": "—",
            "agua": "—",
        },
        "ingredientes": ["Leche líquida", "Azúcar", "Mango", "Pollo", "Harina de trigo", "Mantequilla", "Pasta", "Sal"],
        "pasos": [
            "Licuar el jugo de fruta en leche líquida con azúcar.",
            "Cocinar el pollo y preparar en salsa blanca suave.",
            "Cocinar la pasta al dente y servir caliente.",
        ],
    },
    {
        "numeroMenu": 3,
        "semana": 1,
        "seccion": "Desayuno",
        "nombre_plato": "Arepa con chocolate",
        "componentes": {
            "bebida_leche": "Chocolate en leche",
            "proteico": "—",
            "cereal": "Arepa de maíz",
            "fruta": "Banano",
            "agua": "—",
        },
        "ingredientes": ["Chocolate", "Leche líquida", "Azúcar", "Harina de maíz", "Mantequilla", "Sal", "Banano"],
        "pasos": [
            "Preparar el chocolate en leche líquida caliente con azúcar.",
            "Asar la arepa de maíz en plancha limpia.",
            "Lavar y entregar el banano fresco para el servicio.",
        ],
    },
    {
        "numeroMenu": 4,
        "semana": 1,
        "seccion": "Almuerzo",
        "nombre_plato": "Lentejas con arroz",
        "componentes": {
            "bebida_leche": "Jugo de fruta en leche",
            "proteico": "Lentejas con papa guisada",
            "cereal": "Arroz blanco",
            "fruta": "—",
            "agua": "—",
        },
        "ingredientes": ["Leche líquida", "Azúcar", "Mango", "Lentejas", "Papa", "Tomate", "Cebolla", "Ajo", "Arroz", "Aceite vegetal", "Sal"],
        "pasos": [
            "Preparar el jugo de fruta en leche líquida.",
            "Cocinar las lentejas guisadas con papa, tomate y cebolla.",
            "Preparar el arroz blanco con ajo y servir con las leguminosas.",
        ],
    },
    {
        "numeroMenu": 5,
        "semana": 1,
        "seccion": "Desayuno",
        "nombre_plato": "Torta de huevo con arroz",
        "componentes": {
            "bebida_leche": "Bebida dulce en leche",
            "proteico": "Torta de huevo",
            "cereal": "Arroz blanco",
            "fruta": "—",
            "agua": "—",
        },
        "ingredientes": ["Leche líquida", "Azúcar", "Huevos", "Tomate", "Cebolla", "Arroz", "Ajo", "Aceite vegetal", "Sal"],
        "pasos": [
            "Preparar la bebida dulce en leche líquida con azúcar.",
            "Cocinar completamente la torta de huevo con tomate y cebolla picada.",
            "Acompañar con arroz blanco recién hecho con ajo y sal.",
        ],
    },
    {
        "numeroMenu": 6,
        "semana": 2,
        "seccion": "Almuerzo",
        "nombre_plato": "Carne guisada con arroz",
        "componentes": {
            "bebida_leche": "Refresco de avena",
            "proteico": "Carne de res guisada",
            "cereal": "Arroz blanco",
            "fruta": "—",
            "agua": "—",
        },
        "ingredientes": ["Avena", "Leche líquida", "Azúcar", "Carne de res", "Tomate", "Cebolla", "Pimentón", "Ajo", "Arroz", "Aceite vegetal", "Sal"],
        "pasos": [
            "Preparar el refresco de avena en leche líquida con azúcar.",
            "Guisar la carne de res con tomate, cebolla y pimentón hasta que esté tierna.",
            "Servir acompañada de arroz blanco con ajo.",
        ],
    },
    {
        "numeroMenu": 7,
        "semana": 2,
        "seccion": "Merienda",
        "nombre_plato": "Hojaldras con chocolate",
        "componentes": {
            "bebida_leche": "Chocolate en leche",
            "proteico": "—",
            "cereal": "Hojaldras",
            "fruta": "Papaya",
            "agua": "Agua potable",
        },
        "ingredientes": ["Chocolate", "Leche líquida", "Azúcar", "Harina de trigo", "Polvo de hornear", "Aceite vegetal", "Sal", "Papaya"],
        "pasos": [
            "Preparar el chocolate en leche líquida caliente.",
            "Elaborar y freír las hojaldras hasta dorar ligeramente.",
            "Porcionar la papaya limpia y entregar con agua potable.",
        ],
    },
    {
        "numeroMenu": 8,
        "semana": 2,
        "seccion": "Almuerzo",
        "nombre_plato": "Frijoles guisados con arroz",
        "componentes": {
            "bebida_leche": "Bebida dulce en leche",
            "proteico": "Frijoles guisados con papa",
            "cereal": "Arroz con fideos",
            "fruta": "—",
            "agua": "—",
        },
        "ingredientes": ["Leche líquida", "Azúcar", "Frijoles", "Papa", "Tomate", "Cebolla", "Ajo", "Arroz", "Pasta", "Aceite vegetal", "Sal"],
        "pasos": [
            "Preparar la bebida dulce en leche líquida con azúcar.",
            "Cocinar los frijoles guisados con papa suave.",
            "Preparar el arroz con fideos dorados y servir.",
        ],
    },
    {
        "numeroMenu": 9,
        "semana": 2,
        "seccion": "Merienda",
        "nombre_plato": "Galleta cuca con leche",
        "componentes": {
            "bebida_leche": "Leche líquida",
            "proteico": "Galleta",
            "cereal": "Maní salado",
            "fruta": "Mango",
            "agua": "—",
        },
        "ingredientes": ["Leche líquida", "Galleta", "Maní salado", "Mango"],
        "pasos": [
            "Servir la porción de leche líquida pasteurizada.",
            "Acompañar con galleta y maní salado.",
            "Entregar con mango lavado y porcionado.",
        ],
    },
    {
        "numeroMenu": 10,
        "semana": 2,
        "seccion": "Desayuno",
        "nombre_plato": "Huevos revueltos con arroz",
        "componentes": {
            "bebida_leche": "Jugo de fruta en leche",
            "proteico": "Huevos revueltos",
            "cereal": "Arroz blanco",
            "fruta": "—",
            "agua": "—",
        },
        "ingredientes": ["Leche líquida", "Azúcar", "Mango", "Huevos", "Arroz", "Ajo", "Aceite vegetal", "Sal"],
        "pasos": [
            "Preparar el jugo de fruta en leche líquida.",
            "Cocinar los huevos revueltos bien cocidos en sartén caliente.",
            "Servir con arroz blanco recién hecho con ajo y sal.",
        ],
    },
    {
        "numeroMenu": 11,
        "semana": 3,
        "seccion": "Almuerzo",
        "nombre_plato": "Pollo guisado con arroz",
        "componentes": {
            "bebida_leche": "Refresco de avena",
            "proteico": "Pollo guisado",
            "cereal": "Arroz blanco",
            "fruta": "—",
            "agua": "—",
        },
        "ingredientes": ["Avena", "Leche líquida", "Azúcar", "Pollo", "Tomate", "Cebolla", "Pimentón", "Ajo", "Papa", "Arroz", "Aceite vegetal", "Sal"],
        "pasos": [
            "Preparar el refresco de avena en leche líquida con azúcar.",
            "Cocinar el pollo guisado con tomate, cebolla, pimentón y papa.",
            "Servir con arroz blanco caliente.",
        ],
    },
    {
        "numeroMenu": 12,
        "semana": 3,
        "seccion": "Merienda",
        "nombre_plato": "Torta pastel con yogurt",
        "componentes": {
            "bebida_leche": "Yogurt",
            "proteico": "—",
            "cereal": "Torta pastel",
            "fruta": "Manzana",
            "agua": "—",
        },
        "ingredientes": ["Yogurt", "Harina de trigo", "Huevos", "Azúcar", "Mantequilla", "Polvo de hornear", "Leche líquida", "Manzana"],
        "pasos": [
            "Servir el yogurt frío.",
            "Entregar con porción individual de torta pastel.",
            "Acompañar con manzana lavada y desinfectada.",
        ],
    },
    {
        "numeroMenu": 13,
        "semana": 3,
        "seccion": "Almuerzo",
        "nombre_plato": "Arroz con cerdo y verduras",
        "componentes": {
            "bebida_leche": "Jugo de fruta en leche",
            "proteico": "Carne de cerdo y verduras",
            "cereal": "Arroz",
            "fruta": "—",
            "agua": "Agua potable",
        },
        "ingredientes": ["Leche líquida", "Azúcar", "Mango", "Carne de cerdo", "Arroz", "Zanahoria", "Pimentón", "Ajo", "Aceite vegetal", "Sal"],
        "pasos": [
            "Preparar el jugo de fruta en leche líquida.",
            "Cocinar la carne de cerdo salteada con verduras e integrar con el arroz.",
            "Servir caliente con agua potable.",
        ],
    },
    {
        "numeroMenu": 14,
        "semana": 4,
        "seccion": "Merienda",
        "nombre_plato": "Arroz con leche y galletas",
        "componentes": {
            "bebida_leche": "Arroz con leche y canela",
            "proteico": "—",
            "cereal": "Galleta tipo crackers",
            "fruta": "Papaya",
            "agua": "Agua potable",
        },
        "ingredientes": ["Arroz", "Leche líquida", "Azúcar", "Canela", "Galleta tipo crackers", "Papaya"],
        "pasos": [
            "Preparar el arroz con leche líquida, azúcar y canela.",
            "Acompañar con galleta tipo crackers.",
            "Entregar con porción de papaya fresca y agua potable.",
        ],
    },
    {
        "numeroMenu": 15,
        "semana": 4,
        "seccion": "Almuerzo",
        "nombre_plato": "Pollo con verduras y papas",
        "componentes": {
            "bebida_leche": "Refresco de avena",
            "proteico": "Pollo en julianas con verduras",
            "cereal": "Papas en casco",
            "fruta": "—",
            "agua": "—",
        },
        "ingredientes": ["Avena", "Leche líquida", "Azúcar", "Pollo", "Zanahoria", "Pimentón", "Cebolla", "Papa", "Aceite vegetal", "Sal"],
        "pasos": [
            "Preparar el refresco de avena en leche líquida con azúcar.",
            "Saltear y cocinar el pollo en julianas con verduras.",
            "Asar las papas en casco al vapor y servir.",
        ],
    },
    {
        "numeroMenu": 16,
        "semana": 4,
        "seccion": "Almuerzo",
        "nombre_plato": "Carne molida con arroz y lentejas",
        "componentes": {
            "bebida_leche": "Jugo de guayaba en leche",
            "proteico": "Carne molida guisada",
            "cereal": "Arroz blanco",
            "fruta": "—",
            "agua": "—",
        },
        "ingredientes": ["Leche líquida", "Guayaba", "Azúcar", "Carne molida", "Tomate", "Cebolla", "Arroz", "Lentejas", "Aceite vegetal", "Sal"],
        "pasos": [
            "Preparar el jugo de guayaba en leche líquida.",
            "Cocinar la carne molida guisada y las lentejas tiernas.",
            "Servir con arroz blanco con ajo.",
        ],
    },
    {
        "numeroMenu": 17,
        "semana": 4,
        "seccion": "Desayuno",
        "nombre_plato": "Huevos rancheros con arepa",
        "componentes": {
            "bebida_leche": "Chocolate caliente en leche",
            "proteico": "Huevos rancheros",
            "cereal": "Arepa de choclo",
            "fruta": "—",
            "agua": "—",
        },
        "ingredientes": ["Chocolate", "Leche líquida", "Azúcar", "Huevos", "Tomate", "Cebolla", "Maíz", "Sal", "Mantequilla"],
        "pasos": [
            "Preparar el chocolate espumoso en leche líquida.",
            "Preparar los huevos rancheros con ahogado de tomate y cebolla.",
            "Asar la arepa de choclo y servir caliente.",
        ],
    },
    {
        "numeroMenu": 18,
        "semana": 4,
        "seccion": "Almuerzo",
        "nombre_plato": "Sancocho de pollo escolar",
        "componentes": {
            "bebida_leche": "Jugo de mango en agua",
            "proteico": "Pollo cocido en sancocho",
            "cereal": "Arroz blanco",
            "fruta": "Ensalada de zanahoria",
            "agua": "—",
        },
        "ingredientes": ["Pollo", "Plátano verde", "Yuca", "Papa", "Cebolla", "Cilantro", "Arroz", "Zanahoria", "Sal"],
        "pasos": [
            "Cocinar el sancocho con pollo, plátano, yuca y papa hasta espesar suave.",
            "Servir con arroz blanco caliente y ensalada de zanahoria rallada.",
            "Acompañar con jugo de fruta fresca.",
        ],
    },
    {
        "numeroMenu": 19,
        "semana": 4,
        "seccion": "Merienda",
        "nombre_plato": "Colada de avena con pan de queso",
        "componentes": {
            "bebida_leche": "Colada de avena en leche",
            "proteico": "—",
            "cereal": "Pan de queso",
            "fruta": "Mandarina",
            "agua": "—",
        },
        "ingredientes": ["Avena", "Leche líquida", "Canela", "Azúcar", "Pan de queso", "Mandarina"],
        "pasos": [
            "Cocinar la colada de avena en leche líquida con canela y azúcar suave.",
            "Servir tibia acompañada de pan de queso.",
            "Entregar con mandarina lavada e individual.",
        ],
    },
    {
        "numeroMenu": 20,
        "semana": 4,
        "seccion": "Almuerzo",
        "nombre_plato": "Pescado o atún con arroz de verduras",
        "componentes": {
            "bebida_leche": "Limonada natural",
            "proteico": "Atún o pescado en guiso",
            "cereal": "Arroz con zanahoria y arvejas",
            "fruta": "—",
            "agua": "Agua potable",
        },
        "ingredientes": ["Atún", "Tomate", "Cebolla", "Arroz", "Zanahoria", "Arvejas", "Aceite vegetal", "Sal", "Limón", "Agua potable"],
        "pasos": [
            "Preparar el arroz con zanahoria y arvejas tiernas.",
            "Saltear el atún o filete con guiso casero de tomate y cebolla.",
            "Acompañar con limonada natural y agua potable.",
        ],
    },
]

# Nombres canónicos de los 20 menús para evitar repetirlos
NOMBRES_20_MENUS_BASE = {
    m["nombre_plato"].strip().lower() for m in CATALOGO_20_MENUS_PAE
}

# ==============================================================================
# TABLA DE GRAMAJES ESTÁNDAR PAE (PORCIÓN EN CRUDO LIMPIO POR NIÑO - PRIMARIA)
# ==============================================================================
GRAMAJES_POR_NINO_PRIMARIA = {
    # Proteínas
    "huevos": {"cantidad": Decimal("1.0"), "unidad": "und", "descripcion": "1 huevo mediano"},
    "huevo": {"cantidad": Decimal("1.0"), "unidad": "und", "descripcion": "1 huevo mediano"},
    "pollo": {"cantidad": Decimal("60.0"), "unidad": "g", "descripcion": "Pechuga o pernil limpio"},
    "pechuga de pollo": {"cantidad": Decimal("60.0"), "unidad": "g", "descripcion": "Pechuga sin piel"},
    "carne de res": {"cantidad": Decimal("60.0"), "unidad": "g", "descripcion": "Carne magra en cubos o molida"},
    "carne molida": {"cantidad": Decimal("60.0"), "unidad": "g", "descripcion": "Carne magra molida"},
    "carne de cerdo": {"cantidad": Decimal("60.0"), "unidad": "g", "descripcion": "Carne magra de cerdo"},
    "pescado": {"cantidad": Decimal("60.0"), "unidad": "g", "descripcion": "Filete limpio"},
    "atún": {"cantidad": Decimal("50.0"), "unidad": "g", "descripcion": "Atún en agua o aceite"},
    "queso": {"cantidad": Decimal("30.0"), "unidad": "g", "descripcion": "Queso campesino o cuajada"},
    # Leguminosas
    "lentejas": {"cantidad": Decimal("35.0"), "unidad": "g", "descripcion": "Lenteja seca"},
    "frijol": {"cantidad": Decimal("35.0"), "unidad": "g", "descripcion": "Fríjol seco"},
    "frijoles": {"cantidad": Decimal("35.0"), "unidad": "g", "descripcion": "Fríjol seco"},
    "garbanzos": {"cantidad": Decimal("35.0"), "unidad": "g", "descripcion": "Garbanzo seco"},
    # Cereales y Tubérculos
    "arroz": {"cantidad": Decimal("45.0"), "unidad": "g", "descripcion": "Arroz blanco en grano"},
    "arroz blanco": {"cantidad": Decimal("45.0"), "unidad": "g", "descripcion": "Arroz blanco en grano"},
    "pasta": {"cantidad": Decimal("45.0"), "unidad": "g", "descripcion": "Pasta seca"},
    "arepa": {"cantidad": Decimal("50.0"), "unidad": "g", "descripcion": "Arepa de maíz"},
    "harina de maíz": {"cantidad": Decimal("40.0"), "unidad": "g", "descripcion": "Harina precocida"},
    "harina de trigo": {"cantidad": Decimal("35.0"), "unidad": "g", "descripcion": "Harina de trigo"},
    "papa": {"cantidad": Decimal("70.0"), "unidad": "g", "descripcion": "Papa pastusa o capira"},
    "yuca": {"cantidad": Decimal("60.0"), "unidad": "g", "descripcion": "Yuca fresca limpia"},
    "plátano": {"cantidad": Decimal("50.0"), "unidad": "g", "descripcion": "Plátano verde o maduro"},
    "avena": {"cantidad": Decimal("25.0"), "unidad": "g", "descripcion": "Avena en hojuelas o molida"},
    "galleta": {"cantidad": Decimal("30.0"), "unidad": "g", "descripcion": "Galleta tipo cracker o dulce"},
    "pan": {"cantidad": Decimal("40.0"), "unidad": "g", "descripcion": "Pan escolar"},
    # Lácteos y Líquidos
    "leche": {"cantidad": Decimal("200.0"), "unidad": "ml", "descripcion": "Leche entera pasteurizada"},
    "leche líquida": {"cantidad": Decimal("200.0"), "unidad": "ml", "descripcion": "Leche pasteurizada"},
    "yogurt": {"cantidad": Decimal("150.0"), "unidad": "ml", "descripcion": "Yogurt con probióticos"},
    "chocolate": {"cantidad": Decimal("15.0"), "unidad": "g", "descripcion": "Pastilla o cocoa"},
    # Verduras y Frutas
    "tomate": {"cantidad": Decimal("20.0"), "unidad": "g", "descripcion": "Tomate maduro para guiso"},
    "cebolla": {"cantidad": Decimal("15.0"), "unidad": "g", "descripcion": "Cebolla cabezona o larga"},
    "zanahoria": {"cantidad": Decimal("25.0"), "unidad": "g", "descripcion": "Zanahoria cruda limpia"},
    "pimentón": {"cantidad": Decimal("10.0"), "unidad": "g", "descripcion": "Pimentón fresco"},
    "fruta": {"cantidad": Decimal("100.0"), "unidad": "g", "descripcion": "Fruta entera o en porción"},
    "banano": {"cantidad": Decimal("1.0"), "unidad": "und", "descripcion": "1 unidad mediana"},
    "mango": {"cantidad": Decimal("100.0"), "unidad": "g", "descripcion": "Mango fresco en porción"},
    "papaya": {"cantidad": Decimal("100.0"), "unidad": "g", "descripcion": "Papaya fresca en dados"},
    "mandarina": {"cantidad": Decimal("1.0"), "unidad": "und", "descripcion": "1 unidad fresca"},
    "manzana": {"cantidad": Decimal("1.0"), "unidad": "und", "descripcion": "1 unidad fresca"},
    # Grasas y Condimentos
    "aceite vegetal": {"cantidad": Decimal("5.0"), "unidad": "ml", "descripcion": "Aceite vegetal comestible"},
    "mantequilla": {"cantidad": Decimal("5.0"), "unidad": "g", "descripcion": "Mantequilla o margarina"},
    "azúcar": {"cantidad": Decimal("10.0"), "unidad": "g", "descripcion": "Azúcar para bebida"},
    "sal": {"cantidad": Decimal("1.5"), "unidad": "g", "descripcion": "Sal yodada fluorada"},
    "ajo": {"cantidad": Decimal("1.0"), "unidad": "g", "descripcion": "Ajo fresco"},
}


def resolver_gramaje_por_nino(nombre_ingrediente: str, seccion_nombre: str) -> dict:
    """Busca o infiere el gramaje unitario por niño para el ingrediente según la resolución PAE."""
    nombre_low = nombre_ingrediente.strip().lower()
    for clave, datos in GRAMAJES_POR_NINO_PRIMARIA.items():
        if clave in nombre_low or nombre_low in clave:
            return datos

    # Valores por defecto razonables según palabras clave
    if any(k in nombre_low for k in ["pollo", "carne", "cerdo", "pescado", "atun"]):
        return {"cantidad": Decimal("60.0"), "unidad": "g", "descripcion": "Porción proteica estándar"}
    if any(k in nombre_low for k in ["huevo"]):
        return {"cantidad": Decimal("1.0"), "unidad": "und", "descripcion": "1 unidad"}
    if any(k in nombre_low for k in ["arroz", "pasta", "harina", "arepa"]):
        return {"cantidad": Decimal("45.0"), "unidad": "g", "descripcion": "Cereal base"}
    if any(k in nombre_low for k in ["leche", "yogurt", "jugo"]):
        return {"cantidad": Decimal("200.0"), "unidad": "ml", "descripcion": "Bebida láctea/líquida"}
    if any(k in nombre_low for k in ["aceite"]):
        return {"cantidad": Decimal("5.0"), "unidad": "ml", "descripcion": "Grasa vegetal"}
    if any(k in nombre_low for k in ["sal"]):
        return {"cantidad": Decimal("1.5"), "unidad": "g", "descripcion": "Condimento salino"}

    return {"cantidad": Decimal("25.0"), "unidad": "g", "descripcion": "Porción complementaria"}


def normalizar_texto(texto: str) -> str:
    """Normaliza texto a minúsculas sin tildes ni espacios sobrantes."""
    s = unicodedata.normalize("NFKD", str(texto or "").strip().lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def coincide_ingrediente(nombre_a: str, nombre_b: str) -> bool:
    """Verifica si dos nombres de ingrediente se refieren al mismo alimento sin falsos positivos."""
    a = normalizar_texto(nombre_a)
    b = normalizar_texto(nombre_b)
    if not a or not b:
        return False
    if a == b:
        return True

    palabras_a = set(a.split())
    palabras_b = set(b.split())
    if palabras_a.issubset(palabras_b) or palabras_b.issubset(palabras_a):
        return True

    # Singular/plural simple (huevo/huevos, frijol/frijoles, lenteja/lentejas)
    raiz_a = a[:-2] if a.endswith("es") and len(a) > 4 else (a[:-1] if a.endswith("s") and len(a) > 3 else a)
    raiz_b = b[:-2] if b.endswith("es") and len(b) > 4 else (b[:-1] if b.endswith("s") and len(b) > 3 else b)
    if raiz_a == raiz_b and len(raiz_a) >= 3:
        return True

    # Evitar que palabras muy cortas como "sal" coincidan dentro de "salsa" o "ensalada"
    if len(raiz_a) >= 4 and raiz_a in palabras_b:
        return True
    if len(raiz_b) >= 4 and raiz_b in palabras_a:
        return True
    return False


def buscar_en_mapa_inventario(ing_nombre: str, mapa_inventario: dict) -> dict | None:
    """Busca un ingrediente en el mapa de inventario priorizando coincidencia exacta."""
    clave = normalizar_texto(ing_nombre)
    if clave in mapa_inventario:
        return mapa_inventario[clave]
    for clave_inv, datos_inv in mapa_inventario.items():
        if coincide_ingrediente(ing_nombre, datos_inv.get("nombre", clave_inv)):
            return datos_inv
    return None


def convertir_cantidad_a_unidad_inventario(
    cantidad_base: Decimal,
    unidad_base: str,
    unidad_inv: str,
    factor_inv: Decimal | None = None,
    magnitud_inv: str | None = None,
) -> Decimal:
    """Convierte una cantidad expresada en unidad base (g, ml, und) a la unidad del inventario."""
    u_inv = normalizar_texto(unidad_inv)
    u_base = normalizar_texto(unidad_base)
    mag_inv = (magnitud_inv or "").upper()

    if u_base == "g":
        if u_inv in {"kg", "kilo", "kilos", "kilogramo", "kilogramos"}:
            return (cantidad_base / Decimal("1000.0")).quantize(Decimal("0.01"))
        if u_inv in {"lb", "libra", "libras"}:
            return (cantidad_base / Decimal("500.0")).quantize(Decimal("0.01"))
        if factor_inv and factor_inv > Decimal("1.0") and mag_inv == "MASA":
            return (cantidad_base / factor_inv).quantize(Decimal("0.01"))
    elif u_base == "ml":
        if u_inv in {"l", "lt", "litro", "litros"}:
            return (cantidad_base / Decimal("1000.0")).quantize(Decimal("0.01"))
        if factor_inv and factor_inv > Decimal("1.0") and mag_inv == "VOLUMEN":
            return (cantidad_base / factor_inv).quantize(Decimal("0.01"))
    elif u_base == "und":
        if u_inv in {"cubeta", "cubetas", "panal", "panales"}:
            return (cantidad_base / Decimal("30.0")).quantize(Decimal("0.01"))
        if u_inv in {"docena", "docenas"}:
            return (cantidad_base / Decimal("12.0")).quantize(Decimal("0.01"))
        if factor_inv and factor_inv > Decimal("1.0") and mag_inv in {"UNIDAD", "CANTIDAD"}:
            return (cantidad_base / factor_inv).quantize(Decimal("0.01"))

    return cantidad_base.quantize(Decimal("0.01"))


def convertir_stock_a_unidad_base(
    stock_inv: Decimal,
    unidad_inv: str,
    unidad_base: str,
    factor_inv: Decimal | None = None,
    magnitud_inv: str | None = None,
) -> Decimal:
    """Convierte el stock disponible en la unidad de inventario hacia la unidad base (g, ml, und)."""
    u_inv = normalizar_texto(unidad_inv)
    u_base = normalizar_texto(unidad_base)
    mag_inv = (magnitud_inv or "").upper()

    if u_base == "g":
        if u_inv in {"kg", "kilo", "kilos", "kilogramo", "kilogramos"}:
            return stock_inv * Decimal("1000.0")
        if u_inv in {"lb", "libra", "libras"}:
            return stock_inv * Decimal("500.0")
        if factor_inv and factor_inv > Decimal("1.0") and mag_inv == "MASA":
            return stock_inv * factor_inv
    elif u_base == "ml":
        if u_inv in {"l", "lt", "litro", "litros"}:
            return stock_inv * Decimal("1000.0")
        if factor_inv and factor_inv > Decimal("1.0") and mag_inv == "VOLUMEN":
            return stock_inv * factor_inv
    elif u_base == "und":
        if u_inv in {"cubeta", "cubetas", "panal", "panales"}:
            return stock_inv * Decimal("30.0")
        if u_inv in {"docena", "docenas"}:
            return stock_inv * Decimal("12.0")
        if factor_inv and factor_inv > Decimal("1.0") and mag_inv in {"UNIDAD", "CANTIDAD"}:
            return stock_inv * factor_inv

    return stock_inv


def clasificar_grupo_alimento(nombre_ingrediente: str) -> str:
    """Clasifica un ingrediente en su grupo alimenticio para validar coherencia por momento del día."""
    n = normalizar_texto(nombre_ingrediente)
    if any(k in n for k in ["huevo", "queso", "cuajada", "jamon"]):
        return "proteina_desayuno"
    if any(k in n for k in ["pollo", "pechuga", "carne", "res", "cerdo", "pescado", "atun", "lenteja", "frijol", "garbanzo"]):
        return "proteina_almuerzo"
    if any(k in n for k in ["leche", "yogur", "chocolate", "cocoa", "kumis"]):
        return "lacteo_bebida"
    if any(k in n for k in ["banano", "mango", "papaya", "manzana", "mandarina", "guayaba", "naranja", "pera", "fresa", "mora", "pina", "sandia", "melon", "fruta", "limon"]):
        return "fruta"
    if any(k in n for k in ["arroz", "pasta", "fideo", "arepa", "harina", "pan", "avena", "galleta", "papa", "yuca", "platano", "maiz", "torta", "hojaldra"]):
        return "cereal"
    if any(k in n for k in ["tomate", "cebolla", "zanahoria", "pimenton", "cilantro", "espinaca", "lechuga", "repollo", "ahuyama", "habichuela", "brocoli", "pepino", "arveja"]):
        return "verdura"
    if any(k in n for k in ["sal", "aceite", "mantequilla", "margarina", "azucar", "panela", "ajo", "canela", "polvo de hornear", "agua", "comino", "color", "pimienta"]):
        return "condimento"
    return "otro"


def evaluar_inventario_para_ninos(
    mapa_inventario: dict,
    ninos_presentes: int,
    seccion_nombre: str,
) -> tuple[list[dict], list[dict], int]:
    """
    Evalúa cada alimento del inventario real contra el consumo requerido para `ninos_presentes`.
    Retorna: (ingredientes_suficientes, ingredientes_insuficientes, ninos_maximos_atendibles).
    """
    suficientes = []
    insuficientes = []
    max_ninos_principales = []

    for datos_inv in mapa_inventario.values():
        nombre = datos_inv["nombre"]
        datos_gramaje = resolver_gramaje_por_nino(nombre, seccion_nombre)
        cant_nino = datos_gramaje["cantidad"]
        unidad_base = datos_gramaje["unidad"]
        cant_total_base = cant_nino * Decimal(ninos_presentes)

        unidad_inv = datos_inv["unidad"]
        factor_inv = datos_inv.get("factor_conversion_base")
        magnitud_inv = datos_inv.get("tipo_magnitud")
        stock_actual = datos_inv["cantidad_actual"]

        cant_req_inv = convertir_cantidad_a_unidad_inventario(
            cant_total_base, unidad_base, unidad_inv, factor_inv, magnitud_inv
        )
        stock_en_base = convertir_stock_a_unidad_base(
            stock_actual, unidad_inv, unidad_base, factor_inv, magnitud_inv
        )
        ninos_que_cubre = int(stock_en_base // cant_nino) if cant_nino > 0 else 0
        grupo = clasificar_grupo_alimento(nombre)

        if grupo != "condimento" and ninos_que_cubre > 0:
            max_ninos_principales.append(ninos_que_cubre)

        if stock_actual >= cant_req_inv and ninos_que_cubre >= ninos_presentes:
            suficientes.append({
                **datos_inv,
                "grupo": grupo,
                "cantidad_por_nino": cant_nino,
                "unidad_base": unidad_base,
                "cantidad_requerida_inv": cant_req_inv,
                "ninos_que_cubre": ninos_que_cubre,
            })
        else:
            faltante = max(Decimal("0.0"), cant_req_inv - stock_actual).quantize(Decimal("0.01"))
            insuficientes.append({
                "id_ingrediente": datos_inv["id_ingrediente"],
                "nombre_ingrediente": nombre,
                "stock_actual": str(stock_actual),
                "cantidad_requerida": str(cant_req_inv),
                "faltante": str(faltante),
                "unidad": unidad_inv,
                "ninos_que_cubre": ninos_que_cubre,
                "grupo": grupo,
            })

    ninos_maximos = min(max_ninos_principales) if max_ninos_principales else 0
    return suficientes, insuficientes, ninos_maximos


def tiene_alimentos_principales_para_seccion(
    ingredientes_suficientes: list[dict],
    seccion_nombre: str,
) -> bool:
    """Valida que existan alimentos principales suficientes y coherentes para el momento del día."""
    grupos = {item["grupo"] for item in ingredientes_suficientes}
    if seccion_nombre == "Desayuno":
        return bool(grupos & {"proteina_desayuno", "cereal", "lacteo_bebida", "fruta"})
    if seccion_nombre == "Merienda":
        return bool(grupos & {"lacteo_bebida", "cereal", "fruta", "proteina_desayuno"})
    # Almuerzo
    return bool(grupos & {"proteina_almuerzo", "proteina_desayuno", "cereal", "verdura"})


def construir_sugerencias_adaptadas_al_inventario(
    seccion_nombre: str,
    ingredientes_suficientes: list[dict],
    ninos_presentes: int,
) -> list[dict]:
    """
    Construye propuestas 100% viables usando ÚNICAMENTE los ingredientes que sí alcanzan
    en el inventario real para los `ninos_presentes`. Si no hay alimentos suficientes y coherentes
    para el momento solicitado, retorna lista vacía.
    """
    if not tiene_alimentos_principales_para_seccion(ingredientes_suficientes, seccion_nombre):
        return []

    mapa_suf = {normalizar_texto(it["nombre"]): it for it in ingredientes_suficientes}
    sugerencias: list[dict] = []

    # 1. Intentar primero plantillas innovadoras cuyos ingredientes estén 100% disponibles
    plantillas = PLANTILLAS_INNOVADORAS_PAE.get(seccion_nombre, PLANTILLAS_INNOVADORAS_PAE["Desayuno"])
    for p in plantillas:
        ingredientes_match = []
        completa = True
        for ing_req in p["ingredientes_clave"]:
            match = buscar_en_mapa_inventario(ing_req, mapa_suf)
            if not match:
                completa = False
                break
            if match["nombre"] not in ingredientes_match:
                ingredientes_match.append(match["nombre"])
        if completa and ingredientes_match:
            sugerencias.append({
                "nombre_plato": f"Sugerencia IA: {p['nombre']}",
                "componentes_detalle": p["componentes_detalle"],
                "ingredientes_usados": ingredientes_match,
                "pasos": p["pasos"],
            })

    if sugerencias:
        return sugerencias

    # 2. Adaptación dinámica estricta a los alimentos realmente disponibles en bodega
    por_grupo: dict[str, list[dict]] = {
        "proteina_desayuno": [],
        "proteina_almuerzo": [],
        "cereal": [],
        "lacteo_bebida": [],
        "fruta": [],
        "verdura": [],
        "condimento": [],
        "otro": [],
    }
    for it in ingredientes_suficientes:
        por_grupo.setdefault(it["grupo"], []).append(it)

    condimentos_nombres = [it["nombre"] for it in por_grupo["condimento"][:3]]
    verduras_nombres = [it["nombre"] for it in por_grupo["verdura"][:3]]
    frutas_nombres = [it["nombre"] for it in por_grupo["fruta"][:2]]
    lacteos_nombres = [it["nombre"] for it in por_grupo["lacteo_bebida"][:2]]
    cereales_nombres = [it["nombre"] for it in por_grupo["cereal"][:2]]
    prot_des = [it["nombre"] for it in por_grupo["proteina_desayuno"][:2]]
    prot_alm = [it["nombre"] for it in por_grupo["proteina_almuerzo"][:2]]

    def _dedup(lista: list[str]) -> list[str]:
        vistos = set()
        res = []
        for x in lista:
            k = normalizar_texto(x)
            if k not in vistos:
                vistos.add(k)
                res.append(x)
        return res

    if seccion_nombre == "Desayuno":
        principales = _dedup(prot_des + cereales_nombres + lacteos_nombres + frutas_nombres)
        if not principales:
            return []

        usados = _dedup(principales + verduras_nombres[:2] + condimentos_nombres)
        if prot_des and cereales_nombres:
            titulo = f"Sugerencia IA: Preparación matutina de {prot_des[0]} con {cereales_nombres[0]} adaptada al inventario"
        elif lacteos_nombres and cereales_nombres:
            titulo = f"Sugerencia IA: Desayuno escolar de {lacteos_nombres[0]} con {cereales_nombres[0]} adaptado al inventario"
        elif prot_des:
            titulo = f"Sugerencia IA: Desayuno proteico de {prot_des[0]} adaptado al inventario"
        else:
            titulo = f"Sugerencia IA: Desayuno escolar de {', '.join(principales[:2])} adaptado al inventario"

        componentes = {
            "Bebida con leche": ", ".join(lacteos_nombres) if lacteos_nombres else "Agua potable",
            "Alimento proteico": ", ".join(prot_des) if prot_des else "—",
            "Cereal acompañante": ", ".join(cereales_nombres) if cereales_nombres else "—",
            "Fruta": ", ".join(frutas_nombres) if frutas_nombres else "—",
            "Agua": "Agua potable tratada",
        }
        pasos = [
            f"Alistar y verificar las cantidades exactas para {ninos_presentes} raciones usando únicamente el inventario disponible: {', '.join(usados)}.",
            f"Cocinar y preparar {', '.join(principales[:2])} asegurando cocción completa e inocuidad alimentaria.",
            "Porcionar de forma uniforme según los gramajes PAE y servir caliente para el desayuno escolar.",
        ]
        sugerencias.append({
            "nombre_plato": titulo,
            "componentes_detalle": componentes,
            "ingredientes_usados": usados,
            "pasos": pasos,
        })

    elif seccion_nombre == "Merienda":
        principales = _dedup(lacteos_nombres + cereales_nombres + frutas_nombres + prot_des)
        if not principales:
            return []

        usados = _dedup(principales + condimentos_nombres[:2])
        titulo = f"Sugerencia IA: Refrigerio escolar de {' con '.join(principales[:2])} adaptado al inventario"
        componentes = {
            "Bebida con leche": ", ".join(lacteos_nombres) if lacteos_nombres else "Agua potable",
            "Alimento proteico": ", ".join(prot_des) if prot_des else "—",
            "Cereal acompañante": ", ".join(cereales_nombres) if cereales_nombres else "—",
            "Fruta": ", ".join(frutas_nombres) if frutas_nombres else "—",
            "Agua": "Agua potable tratada",
        }
        pasos = [
            f"Alistar y desinfectar los ingredientes disponibles para {ninos_presentes} meriendas: {', '.join(usados)}.",
            f"Preparar y porcionar {', '.join(principales[:2])} conforme al gramaje PAE vigente.",
            "Entregar en porciones individuales limpias durante la jornada escolar.",
        ]
        sugerencias.append({
            "nombre_plato": titulo,
            "componentes_detalle": componentes,
            "ingredientes_usados": usados,
            "pasos": pasos,
        })

    else:
        # Almuerzo: acepta proteínas de almuerzo y, si no hay, huevos/queso como proteína alternativa
        proteinas = _dedup(prot_alm + prot_des)
        principales = _dedup(proteinas + cereales_nombres + verduras_nombres)
        if not principales:
            return []

        usados = _dedup(principales + frutas_nombres[:1] + lacteos_nombres[:1] + condimentos_nombres)
        if proteinas and cereales_nombres:
            titulo = f"Sugerencia IA: Almuerzo escolar de {proteinas[0]} con {cereales_nombres[0]} adaptado al inventario"
        elif proteinas:
            titulo = f"Sugerencia IA: Plato proteico escolar de {proteinas[0]} adaptado al inventario"
        else:
            titulo = f"Sugerencia IA: Preparación de almuerzo con {' y '.join(principales[:2])} adaptada al inventario"

        componentes = {
            "Bebida con leche": ", ".join(lacteos_nombres) if lacteos_nombres else "Agua potable",
            "Alimento proteico": ", ".join(proteinas) if proteinas else "—",
            "Cereal acompañante": ", ".join(cereales_nombres) if cereales_nombres else "—",
            "Verdura / Fruta": ", ".join(verduras_nombres + frutas_nombres) if (verduras_nombres or frutas_nombres) else "—",
            "Agua": "Agua potable tratada",
        }
        pasos = [
            f"Alistar y pesar los ingredientes disponibles con stock suficiente para {ninos_presentes} almuerzos: {', '.join(usados)}.",
            f"Realizar la cocción completa de {', '.join(principales[:3])} cuidando higiene y temperatura de inocuidad.",
            "Servir las raciones calientes y homogéneas de acuerdo con los gramajes PAE.",
        ]
        sugerencias.append({
            "nombre_plato": titulo,
            "componentes_detalle": componentes,
            "ingredientes_usados": usados,
            "pasos": pasos,
        })

    return sugerencias


def convertir_a_unidad_mayor(cantidad: Decimal, unidad: str) -> tuple[Decimal, str]:
    """Convierte gramos a kilogramos o mililitros a litros si la cantidad es grande."""
    if unidad == "g" and cantidad >= 1000:
        return (cantidad / Decimal("1000.0")).quantize(Decimal("0.01")), "kg"
    if unidad == "ml" and cantidad >= 1000:
        return (cantidad / Decimal("1000.0")).quantize(Decimal("0.01")), "L"
    return cantidad.quantize(Decimal("0.01")), unidad


def obtener_nombre_seccion(id_seccion: int) -> str:
    mapeo = {1: "Desayuno", 2: "Almuerzo", 3: "Merienda"}
    if id_seccion in mapeo:
        return mapeo[id_seccion]
    try:
        sec = SeccionMenu.objects.get(pk=id_seccion)
        if sec.nombre_seccion:
            nombre = sec.nombre_seccion.strip().capitalize()
            if "desayuno" in nombre.lower():
                return "Desayuno"
            if "almuerzo" in nombre.lower():
                return "Almuerzo"
            if "merienda" in nombre.lower() or "refrigerio" in nombre.lower():
                return "Merienda"
            return nombre
    except Exception:
        pass
    return "Desayuno" if id_seccion == 1 else ("Merienda" if id_seccion == 3 else "Almuerzo")


# ==============================================================================
# MOTOR DETERMINÍSTICO DE PROPUESTAS INNOVADORAS POR MOMENTO (FALLBACK INTELIGENTE)
# ==============================================================================
PLANTILLAS_INNOVADORAS_PAE = {
    "Desayuno": [
        {
            "nombre": "Huevos campesinos al gratín con arepa tostada y chocolate en leche",
            "componentes_detalle": {
                "Bebida con leche": "Chocolate caliente en leche",
                "Alimento proteico": "Huevos campesinos con tomate y queso",
                "Cereal acompañante": "Arepa de maíz tostada",
                "Fruta": "Fruta fresca de temporada",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Huevos", "Tomate", "Cebolla", "Queso", "Harina de maíz", "Chocolate", "Leche líquida", "Aceite vegetal", "Sal"],
            "pasos": [
                "Preparar el chocolate espumoso en leche líquida caliente.",
                "Batir los huevos y sofreír con tomate maduro, cebolla picada y cubitos de queso.",
                "Asar las arepas de maíz en plancha limpia y servir recién tostadas con agua potable.",
            ],
        },
        {
            "nombre": "Huevos revueltos a la huerta con porción de arroz blanco y colada de avena",
            "componentes_detalle": {
                "Bebida con leche": "Colada de avena tibia",
                "Alimento proteico": "Huevos revueltos con zanahoria rallada",
                "Cereal acompañante": "Arroz blanco ligero",
                "Fruta": "Banano",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Huevos", "Zanahoria", "Arroz", "Avena", "Leche líquida", "Banano", "Aceite vegetal", "Sal"],
            "pasos": [
                "Cocinar la avena en leche líquida con canela y azúcar suave.",
                "Saltear la zanahoria rallada finamente e integrar a los huevos revueltos bien cocidos.",
                "Servir acompañado de una porción moderada de arroz blanco y banano fresco.",
            ],
        },
        {
            "nombre": "Tortilla escolar dorada de huevo y queso con masitas de maíz y leche tibia",
            "componentes_detalle": {
                "Bebida con leche": "Leche líquida tibia con panela o cocoa",
                "Alimento proteico": "Tortilla de huevo y queso",
                "Cereal acompañante": "Masitas horneadas de maíz",
                "Fruta": "Mandarina",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Huevos", "Queso", "Harina de maíz", "Leche líquida", "Mandarina", "Aceite vegetal", "Sal"],
            "pasos": [
                "Servir la leche líquida pasteurizada tibia.",
                "Elaborar las tortillas de huevo con queso campesino rallado hasta dorar por ambos lados.",
                "Hornear las masitas de maíz y acompañar con mandarina limpia.",
            ],
        },
    ],
    "Almuerzo": [
        {
            "nombre": "Guiso dorado de pollo con arveja y zanahoria, arroz parbolizado y ensalada",
            "componentes_detalle": {
                "Bebida con leche": "Jugo de fruta en leche líquida",
                "Alimento proteico": "Pechuga de pollo en guiso suave de verduras",
                "Cereal acompañante": "Arroz con cilantro",
                "Fruta": "Ensalada de zanahoria y tomate",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Pollo", "Zanahoria", "Tomate", "Cebolla", "Arroz", "Leche líquida", "Aceite vegetal", "Sal"],
            "pasos": [
                "Cocinar el pollo en julianas con guiso casero de tomate, cebolla y zanahoria.",
                "Preparar el arroz blanco con ajo y un toque de cilantro.",
                "Servir con jugo de fruta en leche líquida y ensalada fresca.",
            ],
        },
        {
            "nombre": "Potaje escolar de lentejas con trocitos de carne, arroz blanco y papas al vapor",
            "componentes_detalle": {
                "Bebida con leche": "Refresco de avena fría",
                "Alimento proteico": "Potaje de lentejas con carne magra",
                "Cereal acompañante": "Arroz blanco",
                "Fruta": "Papaya picada",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Carne de res", "Lentejas", "Papa", "Arroz", "Avena", "Leche líquida", "Tomate", "Cebolla", "Aceite vegetal", "Sal"],
            "pasos": [
                "Remojar y cocinar las lentejas con dados de carne magra, papa y guiso aromático.",
                "Preparar el arroz blanco tradicional.",
                "Servir con refresco de avena en leche líquida y porción de papaya.",
            ],
        },
        {
            "nombre": "Pasta a la jardinera con pollo desmechado, salsa de tomate natural y fruta",
            "componentes_detalle": {
                "Bebida con leche": "Bebida láctea de fruta",
                "Alimento proteico": "Pollo desmechado en salsa de tomate natural",
                "Cereal acompañante": "Pasta corta",
                "Fruta": "Mango fresco",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Pollo", "Pasta", "Tomate", "Cebolla", "Zanahoria", "Leche líquida", "Mango", "Aceite vegetal", "Sal"],
            "pasos": [
                "Cocinar la pechuga de pollo y desmechar.",
                "Elaborar una salsa de tomate casera con zanahoria y cebolla e incorporar el pollo y la pasta.",
                "Acompañar con mango porcionado y bebida láctea.",
            ],
        },
    ],
    "Merienda": [
        {
            "nombre": "Colada tibia de fécula de maíz en leche con galletas integrales y fruta",
            "componentes_detalle": {
                "Bebida con leche": "Colada de maizena en leche",
                "Alimento proteico": "—",
                "Cereal acompañante": "Galletas escolares",
                "Fruta": "Manzana fresca",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Leche líquida", "Harina de maíz", "Azúcar", "Galleta", "Manzana"],
            "pasos": [
                "Hervir la leche líquida con fécula o maizena y azúcar suave hasta espesar.",
                "Entregar con porción individual de galletas.",
                "Acompañar con manzana desinfectada.",
            ],
        },
        {
            "nombre": "Yogurt con trocitos de papaya fresca y arepitas dulces de maíz",
            "componentes_detalle": {
                "Bebida con leche": "Yogurt de frutas",
                "Alimento proteico": "—",
                "Cereal acompañante": "Arepitas dulces horneadas",
                "Fruta": "Papaya picada",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Yogurt", "Papaya", "Harina de maíz", "Leche líquida", "Azúcar"],
            "pasos": [
                "Servir el yogurt refrigerado.",
                "Asar las arepitas dulces de maíz en plancha limpia.",
                "Servir con dados de papaya fresca.",
            ],
        },
    ],
}


def generar_con_openai(
    seccion_nombre: str,
    ninos_presentes: int,
    inventario_nombres: list[str],
    preferencia: str,
) -> list[dict] | None:
    """Invoca la API de OpenAI para generar recetas innovadoras y coherentes."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        ejemplos_base = [
            f"- Menú #{m['numeroMenu']} ({m['seccion']}): {m['nombre_plato']}"
            for m in CATALOGO_20_MENUS_PAE
            if m["seccion"].lower() == seccion_nombre.lower()
        ]
        ejemplos_str = "\n".join(ejemplos_base[:8])

        prompt_sistema = (
            "Eres un nutricionista experto y chef del Programa de Alimentación Escolar (PAE) en Colombia. "
            "Tu misión es proponer menús escolares saludables, nutritivos, viables en cocinas institucionales "
            "y estrictamente coherentes con el momento del día solicitado."
        )

        reglas_momento = ""
        if seccion_nombre == "Desayuno":
            reglas_momento = (
                "REGLA OBLIGATORIA PARA DESAYUNO: Debe ser una comida matutina ligera y nutritiva basada en: "
                "Huevos (pericos, revueltos, rancheros, en torta), quesos, arepas, masas, avena, chocolate en leche, "
                "café con leche, porción ligera de arroz o pan, y fruta. "
                "ESTÁ ESTRICTAMENTE PROHIBIDO generar platos pesados de almuerzo como carnes sudadas, carne asada, "
                "pollo asado/entero, frijoles o sancochos pesados."
            )
        elif seccion_nombre == "Merienda":
            reglas_momento = (
                "REGLA OBLIGATORIA PARA MERIENDA: Debe ser un refrigerio complementario ligero: "
                "Bebida láctea (yogurt, leche, colada, avena) + Cereal ligero (galleta, torta, pan, masita) + Fruta fresca."
            )
        else:
            reglas_momento = (
                "REGLA OBLIGATORIA PARA ALMUERZO: Debe ser un plato fuerte completo compuesto por: "
                "Alimento proteico (pollo, carne, cerdo, pescado, huevo) + Cereal (arroz, pasta) + "
                "Leguminosa o verdura + Acompañante + Jugo o agua."
            )

        prompt_usuario = f"""
Genera 1 o 2 propuestas de preparaciones escolares para el momento: **{seccion_nombre}**.
Número de niños beneficiarios: {ninos_presentes} niños de Primaria.
Ingredientes REALES con stock suficiente en el inventario de la sede escolar:
{", ".join(inventario_nombres)}

Preferencia adicional: {preferencia if preferencia else "Sin preferencia específica"}

{reglas_momento}

REGLA CRÍTICA DE INVENTARIO REAL:
- Debes usar **ÚNICAMENTE** ingredientes que aparezcan en la lista anterior.
- **ESTÁ PROHIBIDO** agregar ingredientes que no estén en esa lista (ni siquiera leche, fruta, queso, tomate, sal o aceite si no aparecen listados).
- Si con los ingredientes listados no es posible preparar una comida coherente para {seccion_nombre}, devuelve `"sugerencias": []`.

REGLA DE ORIGINALIDAD:
Los siguientes menús ya están formalmente registrados en el ciclo oficial del PAE para este momento:
{ejemplos_str}
Tus propuestas deben inspirarse en el balance del PAE, pero **NO deben repetir ninguno de los anteriores**.
Deben ser preparaciones NUEVAS, DIFERENTES, apetitosas y viables con lo disponible.

Responde ÚNICAMENTE un objeto JSON válido con la siguiente estructura:
{{
  "sugerencias": [
    {{
      "nombre_plato": "Nombre apetitoso de la preparación",
      "componentes_detalle": {{
        "Bebida con leche": "...",
        "Alimento proteico": "...",
        "Cereal acompañante": "...",
        "Fruta": "...",
        "Agua": "Agua potable tratada"
      }},
      "ingredientes_usados": ["Nombre1", "Nombre2"],
      "pasos": [
        "Paso 1...",
        "Paso 2...",
        "Paso 3..."
      ]
    }}
  ]
}}
"""

        respuesta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            timeout=25,
        )

        contenido = respuesta.choices[0].message.content
        data = json.loads(contenido)
        return data.get("sugerencias")
    except Exception as e:
        logger.warning("Fallo al generar con OpenAI, utilizando motor determinístico: %s", e)
        return None


# ==============================================================================
# ENDPOINT PRINCIPAL: SUGERENCIAS DE RECETAS CON IA E IMPACTO EN INVENTARIO
# ==============================================================================
@api_view(["POST", "GET"])
@permission_classes([AllowAny])
def sugerencias_recetas_ia(request):
    """
    POST /api/ia/sugerencias-recetas/
    Genera menús escolares innovadores coherentes con el momento del día (Desayuno, Almuerzo, Merienda),
    basados en el inventario real de la sede, sin repetir los 20 menús base del PAE,
    y calcula el consumo total y descuento proyectado para N niños de primaria.
    """
    data = request.data if request.method == "POST" else request.query_params

    # Parámetros recibidos
    raw_sede = data.get("id_sede") or data.get("sede")
    raw_ninos = data.get("ninos_presentes") or data.get("ninos") or 100
    raw_seccion = data.get("id_seccion") or data.get("seccion") or 1
    preferencia = str(data.get("preferencia") or "").strip()

    try:
        ninos_presentes = max(1, int(raw_ninos))
    except (ValueError, TypeError):
        ninos_presentes = 100

    try:
        id_seccion = int(raw_seccion)
    except (ValueError, TypeError):
        id_seccion = 1

    seccion_nombre = obtener_nombre_seccion(id_seccion)

    # 1. Obtener inventario REAL de la sede (sin simular stock inexistente)
    id_sede_final = None
    if raw_sede:
        try:
            id_sede_final = int(raw_sede)
        except (ValueError, TypeError):
            pass

    if not id_sede_final and getattr(request.user, "id_sede_id", None):
        id_sede_final = request.user.id_sede_id

    items_inventario_db = []
    if id_sede_final:
        items_inventario_db = list(
            Inventario.objects.filter(id_sede_id=id_sede_final, cantidad_actual__gt=0)
        )
    elif getattr(request.user, "id_institucion_id", None):
        items_inventario_db = list(
            Inventario.objects.filter(
                id_institucion_id=request.user.id_institucion_id,
                cantidad_actual__gt=0,
            )
        )
    else:
        items_inventario_db = list(
            Inventario.objects.filter(cantidad_actual__gt=0)[:100]
        )

    # Mapeo de inventario REAL: clave normalizada -> datos
    mapa_inventario = {}
    if items_inventario_db:
        ids_ing = [it.id_ingrediente for it in items_inventario_db]
        ings_dict = {
            ing.id_ingrediente: ing
            for ing in Ingrediente.objects.filter(id_ingrediente__in=ids_ing).select_related("id_unidad_medida")
        }
        unidades_dict = {
            u.id_unidad_medida: u
            for u in UnidadMedida.objects.all()
        }

        for item in items_inventario_db:
            ing_obj = ings_dict.get(item.id_ingrediente)
            nombre_ing = ing_obj.nombre_ingrediente if ing_obj else f"Ingrediente #{item.id_ingrediente}"
            u_obj = unidades_dict.get(item.id_unidad_medida)
            u_abrev = u_obj.abreviatura if u_obj else "und"
            factor_base = u_obj.factor_conversion_base if u_obj else Decimal("1.0")
            tipo_mag = u_obj.tipo_magnitud if u_obj else None
            clave = normalizar_texto(nombre_ing)

            # Si hubiera varios registros del mismo ingrediente en la consulta, sumar cantidades de la misma unidad
            if clave in mapa_inventario and mapa_inventario[clave]["unidad"] == u_abrev:
                mapa_inventario[clave]["cantidad_actual"] += Decimal(item.cantidad_actual)
            elif clave not in mapa_inventario:
                mapa_inventario[clave] = {
                    "id_inventario": item.id_inventario,
                    "id_ingrediente": item.id_ingrediente,
                    "nombre": nombre_ing,
                    "cantidad_actual": Decimal(item.cantidad_actual),
                    "unidad": u_abrev,
                    "factor_conversion_base": factor_base,
                    "tipo_magnitud": tipo_mag,
                }

    # Evaluar qué alimentos realmente alcanzan para los `ninos_presentes`
    ingredientes_suficientes, ingredientes_insuficientes, ninos_maximos_atendibles = (
        evaluar_inventario_para_ninos(mapa_inventario, ninos_presentes, seccion_nombre)
    )
    hay_base_suficiente = tiene_alimentos_principales_para_seccion(
        ingredientes_suficientes, seccion_nombre
    )

    nombres_suficientes_prompt = [
        f"{it['nombre']} ({it['cantidad_actual']} {it['unidad']})"
        for it in ingredientes_suficientes
    ]

    # 2. Generar sugerencias SOLO si hay alimentos reales suficientes para los N niños
    def _estructurar_y_validar(candidatas: list[dict]) -> list[dict]:
        """Calcula gramajes/stock real y conserva ÚNICAMENTE recetas 100% viables con el inventario."""
        viables = []
        for idx, s in enumerate(candidatas, start=1):
            nombre_plato = str(s.get("nombre_plato") or f"Sugerencia IA #{idx}").strip()
            nombre_lower = nombre_plato.lower().replace("sugerencia ia:", "").strip()
            if nombre_lower in NOMBRES_20_MENUS_BASE:
                nombre_plato = f"Sugerencia IA Alternativa: {nombre_plato} Estilo Casero Escolar"

            componentes_det = s.get("componentes_detalle", {})
            comp_resumen = ", ".join(f"{k}: {v}" for k, v in componentes_det.items() if v and v != "—")
            ing_usados = s.get("ingredientes_usados") or []
            if not ing_usados:
                continue

            lista_ingredientes_resultado = []
            todos_alcanzan = True

            for ing_nombre in ing_usados:
                ing_low = str(ing_nombre).strip().lower()
                datos_gramaje = resolver_gramaje_por_nino(ing_low, seccion_nombre)

                cant_nino = datos_gramaje["cantidad"]
                cant_total = cant_nino * Decimal(ninos_presentes)
                unidad_base = datos_gramaje["unidad"]

                item_inv = buscar_en_mapa_inventario(ing_nombre, mapa_inventario)
                if item_inv:
                    stock_disponible = item_inv["cantidad_actual"]
                    unidad_inv = item_inv["unidad"]
                    factor_inv = item_inv.get("factor_conversion_base")
                    magnitud_inv = item_inv.get("tipo_magnitud")
                    id_ing = item_inv["id_ingrediente"]
                    id_inv = item_inv["id_inventario"]
                    cant_total_unidad_inv = convertir_cantidad_a_unidad_inventario(
                        cant_total, unidad_base, unidad_inv, factor_inv, magnitud_inv
                    )
                    alcanza = stock_disponible >= cant_total_unidad_inv
                else:
                    # El ingrediente NO existe en el inventario real: stock 0 y NO alcanza
                    stock_disponible = Decimal("0.0")
                    unidad_inv = unidad_base
                    id_ing = None
                    id_inv = None
                    cant_total_unidad_inv = cant_total.quantize(Decimal("0.01"))
                    alcanza = False

                stock_restante = max(Decimal("0.0"), stock_disponible - cant_total_unidad_inv)
                if not alcanza:
                    todos_alcanzan = False

                cant_total_mostrada, unidad_mostrada = convertir_a_unidad_mayor(cant_total, unidad_base)

                lista_ingredientes_resultado.append({
                    "id_ingrediente": id_ing,
                    "id_inventario": id_inv,
                    "nombre_ingrediente": item_inv["nombre"] if item_inv else ing_nombre,
                    "cantidad_por_nino": f"{cant_nino} {unidad_base}",
                    "cantidad_por_nino_valor": str(cant_nino),
                    "cantidad_total": f"{cant_total_mostrada} {unidad_mostrada}",
                    "cantidad_total_valor": str(cant_total_unidad_inv),
                    "unidad": unidad_inv,
                    "stock_actual": str(stock_disponible),
                    "stock_restante_proyectado": str(stock_restante.quantize(Decimal("0.01"))),
                    "alcanza": alcanza,
                })

            if todos_alcanzan and lista_ingredientes_resultado:
                viables.append({
                    "id_plato": None,
                    "nombre_plato": nombre_plato,
                    "id_seccion": id_seccion,
                    "seccion_nombre": seccion_nombre,
                    "componente": comp_resumen or "Preparación adaptada al inventario disponible",
                    "componentes_detalle": componentes_det,
                    "ninos_presentes": ninos_presentes,
                    "ingredientes": lista_ingredientes_resultado,
                    "pasos": s.get("pasos", [
                        "Desinfectar superficies, utensilios e ingredientes en la cocina escolar.",
                        "Realizar la cocción completa asegurando temperatura de inocuidad.",
                        "Porcionar de manera homogénea según las cantidades calculadas para los niños.",
                    ]),
                    "origen": "SUGERENCIA_IA",
                    "etiqueta": f"Sugerencia Inteligente para {seccion_nombre} ({ninos_presentes} raciones)",
                    "viable_con_inventario": True,
                })
        return viables

    sugerencias_estructuradas = []
    uso_openai = False

    if hay_base_suficiente:
        sugerencias_openai = generar_con_openai(
            seccion_nombre=seccion_nombre,
            ninos_presentes=ninos_presentes,
            inventario_nombres=nombres_suficientes_prompt,
            preferencia=preferencia,
        )
        if sugerencias_openai:
            sugerencias_estructuradas = _estructurar_y_validar(sugerencias_openai)
            uso_openai = bool(sugerencias_estructuradas)

        if not sugerencias_estructuradas:
            sugerencias_adaptadas = construir_sugerencias_adaptadas_al_inventario(
                seccion_nombre=seccion_nombre,
                ingredientes_suficientes=ingredientes_suficientes,
                ninos_presentes=ninos_presentes,
            )
            sugerencias_estructuradas = _estructurar_y_validar(sugerencias_adaptadas)

    inventario_suficiente = bool(sugerencias_estructuradas)

    # 3. Evaluar platos base PAE estipulados contra el inventario real
    mapa_suf_nombres = {normalizar_texto(it["nombre"]): it for it in ingredientes_suficientes}
    platos_base_pae = []
    for b in CATALOGO_20_MENUS_PAE:
        if b["seccion"].lower() == seccion_nombre.lower():
            base_viable = bool(b["ingredientes"]) and all(
                buscar_en_mapa_inventario(ing_b, mapa_suf_nombres) is not None
                for ing_b in b["ingredientes"]
            )
            platos_base_pae.append({
                "id_plato": None,
                "nombre_plato": b["nombre_plato"],
                "id_seccion": id_seccion,
                "seccion_nombre": b["seccion"],
                "componente": f"{b['componentes']['bebida_leche']}, {b['componentes']['proteico']}, {b['componentes']['cereal']}",
                "componentes_detalle": b["componentes"],
                "ingredientes": b["ingredientes"],
                "pasos": b["pasos"],
                "origen": "PAE_ESTIPULADO",
                "etiqueta": f"Menú Oficial PAE #{b['numeroMenu']}",
                "viable_con_inventario": base_viable,
            })

    todas_las_opciones = sugerencias_estructuradas + [
        p for p in platos_base_pae if p["viable_con_inventario"]
    ]

    if inventario_suficiente:
        texto_resumen = (
            f"Se generaron {len(sugerencias_estructuradas)} propuestas adaptadas al inventario real disponible "
            f"para {seccion_nombre} ({ninos_presentes} niños de Primaria), garantizando que todos los ingredientes "
            "alcanzan con el stock actual y sin repetir los menús oficiales del PAE."
        )
    elif not mapa_inventario:
        texto_resumen = (
            f"No hay alimentos disponibles en el inventario de esta sede. "
            f"No es posible generar recetas de {seccion_nombre} para {ninos_presentes} niños "
            "hasta que se registren existencias en bodega."
        )
    elif ninos_maximos_atendibles > 0 and ninos_maximos_atendibles < ninos_presentes:
        texto_resumen = (
            f"No hay alimentos suficientes en el inventario para preparar {seccion_nombre} para {ninos_presentes} niños. "
            f"Con las existencias actuales solo alcanza para un máximo aproximado de {ninos_maximos_atendibles} niños. "
            "Ajusta la cantidad de raciones o abastece los ingredientes insuficientes."
        )
    else:
        texto_resumen = (
            f"No hay alimentos principales suficientes y coherentes en el inventario para preparar {seccion_nombre} "
            f"para {ninos_presentes} niños. Verifica los ingredientes disponibles o registra nuevas existencias."
        )

    # Sincronizar catálogo base en MongoDB Atlas si aplica
    try:
        sincronizar_catalogo_recetas(CATALOGO_20_MENUS_PAE)
    except Exception:
        pass

    # Registrar el evento en el historial de MongoDB Atlas
    id_registro_mongo = None
    try:
        id_registro_mongo = guardar_historial_sugerencia({
            "id_sede": id_sede_final,
            "seccion": seccion_nombre,
            "id_seccion": id_seccion,
            "ninos_presentes": ninos_presentes,
            "preferencia": preferencia,
            "motor_ia": (
                "OpenAI GPT-4o-mini"
                if uso_openai
                else ("Motor PAE Determinístico" if inventario_suficiente else "Sin stock suficiente")
            ),
            "inventario_suficiente": inventario_suficiente,
            "ninos_maximos_atendibles": ninos_maximos_atendibles,
            "total_sugerencias": len(sugerencias_estructuradas),
            "sugerencias": sugerencias_estructuradas,
            "ingredientes_insuficientes": ingredientes_insuficientes,
            "platos_base_pae_consultados": len(platos_base_pae),
        })
    except Exception as e:
        logger.warning("No se pudo registrar la sugerencia en MongoDB Atlas: %s", e)

    return Response(
        {
            "status": "success",
            "seccion": seccion_nombre,
            "id_seccion": id_seccion,
            "ninos_presentes": ninos_presentes,
            "id_sede": id_sede_final,
            "inventario_suficiente": inventario_suficiente,
            "ninos_maximos_atendibles": ninos_maximos_atendibles,
            "sugerencias": texto_resumen,
            "sugerencias_ia_estructuradas": sugerencias_estructuradas,
            "ingredientes_disponibles_suficientes": [
                {
                    "id_ingrediente": it["id_ingrediente"],
                    "nombre_ingrediente": it["nombre"],
                    "stock_actual": str(it["cantidad_actual"]),
                    "unidad": it["unidad"],
                    "ninos_que_cubre": it["ninos_que_cubre"],
                }
                for it in ingredientes_suficientes
            ],
            "ingredientes_insuficientes": ingredientes_insuficientes,
            "platos_estipulados_pae": platos_base_pae,
            "todas_las_opciones": todas_las_opciones,
            "mongodb_atlas": {
                "activo": bool(id_registro_mongo),
                "id_registro_historial": id_registro_mongo,
            },
        },
        status=status.HTTP_200_OK,
    )


# ==============================================================================
# ENDPOINT: DESCONTAR INVENTARIO TRAS CONFIRMAR LA PREPARACIÓN
# ==============================================================================
@api_view(["POST"])
@permission_classes([AllowAny])
def descontar_inventario_ia(request):
    """
    POST /api/ia/descontar-inventario/
    Aplica el descuento real de los ingredientes utilizados en la preparación escolar sobre
    la tabla Inventario de la sede, y registra las salidas correspondientes.
    """
    data = request.data
    id_sede = data.get("id_sede")
    nombre_preparacion = data.get("nombre_preparacion", "Preparación sugerida por IA")
    ingredientes_a_descontar = data.get("ingredientes", [])
    ninos = data.get("ninos_presentes", 100)

    if not id_sede:
        return Response(
            {"error": "Debes especificar la sede (id_sede) donde se realiza la preparación."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not ingredientes_a_descontar or not isinstance(ingredientes_a_descontar, list):
        return Response(
            {"error": "Debes enviar la lista de ingredientes con las cantidades a descontar."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    descuentos_aplicados = []
    alertas = []

    with transaction.atomic():
        for item in ingredientes_a_descontar:
            id_ing = item.get("id_ingrediente")
            nombre = item.get("nombre_ingrediente", f"Ingrediente #{id_ing}")
            raw_cant = item.get("cantidad_a_descontar") or item.get("cantidad_total_valor") or 0

            try:
                cantidad_descontar = Decimal(str(raw_cant))
            except (InvalidOperation, TypeError, ValueError):
                cantidad_descontar = Decimal("0.0")

            if cantidad_descontar <= Decimal("0.0"):
                continue

            inv_obj = None
            if id_ing:
                inv_obj = (
                    Inventario.objects.select_for_update()
                    .filter(id_sede_id=id_sede, id_ingrediente=id_ing)
                    .first()
                )

            if not inv_obj:
                # Búsqueda por nombre
                ing_match = Ingrediente.objects.filter(nombre_ingrediente__iexact=nombre).first()
                if ing_match:
                    inv_obj = (
                        Inventario.objects.select_for_update()
                        .filter(id_sede_id=id_sede, id_ingrediente=ing_match.id_ingrediente)
                        .first()
                    )

            if inv_obj:
                stock_previo = Decimal(inv_obj.cantidad_actual)
                nuevo_stock = max(Decimal("0.0"), stock_previo - cantidad_descontar)
                inv_obj.cantidad_actual = nuevo_stock
                inv_obj.save(update_fields=["cantidad_actual"])

                # Registrar salida de inventario
                try:
                    SalidaInventario.objects.create(
                        id_ingrediente_id=inv_obj.id_ingrediente,
                        id_usuario=request.user if request.user.is_authenticated else None,
                        fecha=timezone.now(),
                        cantidad=cantidad_descontar,
                        id_unidad_medida_id=inv_obj.id_unidad_medida,
                        observaciones=(
                            f"Consumo preparación '{nombre_preparacion}' para {ninos} niños. "
                            f"Stock anterior: {stock_previo}, nuevo: {nuevo_stock}."
                        ),
                    )
                except Exception as err:
                    logger.warning("No se pudo registrar SalidaInventario formal: %s", err)

                descuentos_aplicados.append({
                    "nombre_ingrediente": nombre,
                    "cantidad_descontada": str(cantidad_descontar),
                    "stock_anterior": str(stock_previo),
                    "nuevo_stock": str(nuevo_stock),
                    "stock_bajo": nuevo_stock <= inv_obj.stock_minimo,
                })
            else:
                alertas.append(
                    f"El ingrediente '{nombre}' no está registrado en el inventario de esta sede."
                )

    # Registrar auditoría del consumo en MongoDB Atlas
    id_auditoria_mongo = None
    try:
        id_auditoria_mongo = guardar_auditoria_consumo({
            "id_sede": id_sede,
            "nombre_preparacion": nombre_preparacion,
            "ninos_presentes": ninos,
            "total_descontados": len(descuentos_aplicados),
            "descuentos": descuentos_aplicados,
            "alertas": alertas,
            "usuario": getattr(request.user, "email", "anonimo") if getattr(request, "user", None) and request.user.is_authenticated else "anonimo",
        })
    except Exception as e:
        logger.warning("No se pudo registrar la auditoría de consumo en MongoDB Atlas: %s", e)

    return Response(
        {
            "status": "success",
            "mensaje": f"Se aplicó el descuento de ingredientes para la preparación '{nombre_preparacion}' ({ninos} raciones).",
            "descuentos": descuentos_aplicados,
            "alertas": alertas,
            "total_ingredientes_descontados": len(descuentos_aplicados),
            "id_auditoria_mongodb": id_auditoria_mongo,
        },
        status=status.HTTP_200_OK,
    )


# ==============================================================================
# ENDPOINT: ESTADO DE CONEXIÓN CON MONGODB ATLAS
# ==============================================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def estado_mongodb_ia(request):
    """
    GET /api/ia/mongodb/status/
    Verifica el estado de conexión activa entre el módulo de IA y MongoDB Atlas.
    """
    estado = verificar_conexion_mongo()
    codigo_http = status.HTTP_200_OK if estado.get("conectado") else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(estado, status=codigo_http)


# ==============================================================================
# ENDPOINT: HISTORIAL DE SUGERENCIAS IA ALMACENADAS EN MONGODB ATLAS
# ==============================================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def historial_sugerencias_ia_view(request):
    """
    GET /api/ia/historial/
    Retorna el historial de sugerencias generadas por la IA almacenadas en MongoDB Atlas.
    Parámetros opcionales: limite, id_sede, seccion
    """
    try:
        limite = max(1, min(100, int(request.query_params.get("limite", 20))))
    except (ValueError, TypeError):
        limite = 20
    id_sede = request.query_params.get("id_sede")
    seccion = request.query_params.get("seccion")

    id_sede_int = None
    if id_sede:
        try:
            id_sede_int = int(id_sede)
        except (ValueError, TypeError):
            pass

    historial = obtener_historial_sugerencias(
        limite=limite,
        id_sede=id_sede_int,
        seccion=seccion,
    )

    return Response(
        {
            "status": "success",
            "total_registros": len(historial),
            "historial": historial,
        },
        status=status.HTTP_200_OK,
    )

