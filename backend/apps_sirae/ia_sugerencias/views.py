import json
import logging
import os
import random
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps_sirae.usuarios.authentication import CustomJWTAuthentication

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
from apps_sirae.ia_sugerencias.imagenes import generar_y_subir_imagen_receta
from apps_sirae.ia_sugerencias.mongodb import (
    guardar_historial_sugerencia,
    obtener_historial_sugerencias,
    guardar_auditoria_consumo,
    verificar_conexion_mongo,
    sincronizar_catalogo_recetas,
)

logger = logging.getLogger(__name__)


class OptionalJWTAuthentication(CustomJWTAuthentication):
    """
    Autenticación JWT tolerante para los endpoints públicos de IA:
    si el frontend envía un token Bearer válido, identifica al usuario (para conocer su sede/institución);
    si envía un token vencido, revocado o malformado, lo ignora en lugar de lanzar error HTTP 401.
    """

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except Exception:
            return None

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
    "papa": {"cantidad": Decimal("70.0"), "unidad": "g", "descripcion": "Papa pastusa, sabanera o criolla"},
    "yuca": {"cantidad": Decimal("60.0"), "unidad": "g", "descripcion": "Yuca fresca limpia"},
    "plátano": {"cantidad": Decimal("50.0"), "unidad": "g", "descripcion": "Plátano verde o maduro"},
    "maíz": {"cantidad": Decimal("40.0"), "unidad": "g", "descripcion": "Maíz tierno o mazorca desgranada"},
    "avena": {"cantidad": Decimal("25.0"), "unidad": "g", "descripcion": "Avena en hojuelas o molida"},
    "galleta": {"cantidad": Decimal("30.0"), "unidad": "g", "descripcion": "Galleta tipo cracker o dulce"},
    "pan de queso": {"cantidad": Decimal("45.0"), "unidad": "g", "descripcion": "Pan de queso o almojábana escolar"},
    "pan": {"cantidad": Decimal("40.0"), "unidad": "g", "descripcion": "Pan escolar"},
    # Lácteos y Líquidos
    "leche": {"cantidad": Decimal("200.0"), "unidad": "ml", "descripcion": "Leche entera pasteurizada"},
    "leche líquida": {"cantidad": Decimal("200.0"), "unidad": "ml", "descripcion": "Leche pasteurizada"},
    "yogurt": {"cantidad": Decimal("150.0"), "unidad": "ml", "descripcion": "Yogurt con probióticos"},
    "chocolate": {"cantidad": Decimal("15.0"), "unidad": "g", "descripcion": "Pastilla de chocolate santafereño o cocoa"},
    # Verduras y Frutas
    "tomate": {"cantidad": Decimal("20.0"), "unidad": "g", "descripcion": "Tomate chonto maduro para hogao"},
    "cebolla": {"cantidad": Decimal("15.0"), "unidad": "g", "descripcion": "Cebolla larga o cabezona para hogao"},
    "zanahoria": {"cantidad": Decimal("25.0"), "unidad": "g", "descripcion": "Zanahoria cruda limpia"},
    "arvejas": {"cantidad": Decimal("20.0"), "unidad": "g", "descripcion": "Arveja verde fresca"},
    "pimentón": {"cantidad": Decimal("10.0"), "unidad": "g", "descripcion": "Pimentón fresco"},
    "cilantro": {"cantidad": Decimal("3.0"), "unidad": "g", "descripcion": "Cilantro fresco picado"},
    "fruta": {"cantidad": Decimal("100.0"), "unidad": "g", "descripcion": "Fruta entera o en porción"},
    "banano": {"cantidad": Decimal("1.0"), "unidad": "und", "descripcion": "1 unidad mediana"},
    "mango": {"cantidad": Decimal("100.0"), "unidad": "g", "descripcion": "Mango fresco en porción"},
    "guayaba": {"cantidad": Decimal("80.0"), "unidad": "g", "descripcion": "Guayaba fresca colombiana"},
    "papaya": {"cantidad": Decimal("100.0"), "unidad": "g", "descripcion": "Papaya fresca en dados"},
    "mandarina": {"cantidad": Decimal("1.0"), "unidad": "und", "descripcion": "1 unidad fresca"},
    "manzana": {"cantidad": Decimal("1.0"), "unidad": "und", "descripcion": "1 unidad fresca"},
    # Grasas y Condimentos
    "aceite vegetal": {"cantidad": Decimal("5.0"), "unidad": "ml", "descripcion": "Aceite vegetal comestible"},
    "mantequilla": {"cantidad": Decimal("5.0"), "unidad": "g", "descripcion": "Mantequilla o margarina"},
    "panela": {"cantidad": Decimal("12.0"), "unidad": "g", "descripcion": "Panela rallada o en bloque"},
    "azúcar": {"cantidad": Decimal("10.0"), "unidad": "g", "descripcion": "Azúcar para bebida"},
    "canela": {"cantidad": Decimal("0.5"), "unidad": "g", "descripcion": "Canela en astilla o molida"},
    "sal": {"cantidad": Decimal("1.5"), "unidad": "g", "descripcion": "Sal yodada fluorada"},
    "ajo": {"cantidad": Decimal("1.0"), "unidad": "g", "descripcion": "Ajo fresco"},
}


def resolver_gramaje_por_nino(nombre_ingrediente: str, seccion_nombre: str) -> dict:
    """Busca o infiere el gramaje unitario por niño para el ingrediente según la resolución PAE."""
    nombre_norm = normalizar_texto(nombre_ingrediente)
    for clave, datos in GRAMAJES_POR_NINO_PRIMARIA.items():
        clave_norm = normalizar_texto(clave)
        if clave_norm == nombre_norm:
            return datos
    for clave, datos in GRAMAJES_POR_NINO_PRIMARIA.items():
        clave_norm = normalizar_texto(clave)
        if clave_norm in nombre_norm or nombre_norm in clave_norm:
            return datos

    # Valores por defecto razonables según palabras clave
    if any(k in nombre_norm for k in ["pollo", "carne", "cerdo", "pescado", "atun"]):
        return {"cantidad": Decimal("60.0"), "unidad": "g", "descripcion": "Porción proteica estándar"}
    if any(k in nombre_norm for k in ["huevo"]):
        return {"cantidad": Decimal("1.0"), "unidad": "und", "descripcion": "1 unidad"}
    if any(k in nombre_norm for k in ["arroz", "pasta", "harina", "arepa", "maiz", "pan"]):
        return {"cantidad": Decimal("45.0"), "unidad": "g", "descripcion": "Cereal base"}
    if any(k in nombre_norm for k in ["leche", "yogur", "jugo"]):
        return {"cantidad": Decimal("200.0"), "unidad": "ml", "descripcion": "Bebida láctea/líquida"}
    if any(k in nombre_norm for k in ["aceite"]):
        return {"cantidad": Decimal("5.0"), "unidad": "ml", "descripcion": "Grasa vegetal"}
    if any(k in nombre_norm for k in ["sal"]):
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


def clasificar_estado_stock(
    stock_actual: Decimal,
    cant_requerida: Decimal,
    stock_minimo: Decimal = Decimal("0.00"),
) -> dict:
    """
    Evalúa el estado real de stock de un ingrediente frente al consumo requerido:
    - AGOTADO ("No hay"): stock_actual <= 0
    - INSUFICIENTE ("Bajo monto / Insuficiente"): 0 < stock_actual < cant_requerida
    - BAJO_STOCK ("Bajo monto"): alcanza para la preparación, pero el stock actual o el restante
      proyectado queda en o por debajo del stock mínimo (o queda exactamente en 0)
    - DISPONIBLE ("Disponible"): alcanza con holgura por encima del stock mínimo
    """
    stock_actual = Decimal(str(stock_actual or 0))
    cant_requerida = Decimal(str(cant_requerida or 0))
    stock_minimo = Decimal(str(stock_minimo or 0))

    stock_restante = max(Decimal("0.00"), stock_actual - cant_requerida).quantize(Decimal("0.01"))
    faltante = max(Decimal("0.00"), cant_requerida - stock_actual).quantize(Decimal("0.01"))

    if stock_actual <= Decimal("0.00"):
        return {
            "alcanza": False,
            "agotado": True,
            "stock_bajo": True,
            "estado_stock": "AGOTADO",
            "estado_stock_label": "No hay",
            "stock_restante_proyectado": Decimal("0.00"),
            "faltante": cant_requerida.quantize(Decimal("0.01")),
        }

    if stock_actual < cant_requerida:
        return {
            "alcanza": False,
            "agotado": False,
            "stock_bajo": True,
            "estado_stock": "INSUFICIENTE",
            "estado_stock_label": "Bajo monto / Insuficiente",
            "stock_restante_proyectado": Decimal("0.00"),
            "faltante": faltante,
        }

    queda_bajo = (
        (stock_minimo > Decimal("0.00") and (stock_actual <= stock_minimo or stock_restante <= stock_minimo))
        or (stock_restante <= Decimal("0.00"))
    )
    if queda_bajo:
        return {
            "alcanza": True,
            "agotado": False,
            "stock_bajo": True,
            "estado_stock": "BAJO_STOCK",
            "estado_stock_label": "Bajo monto",
            "stock_restante_proyectado": stock_restante,
            "faltante": Decimal("0.00"),
        }

    return {
        "alcanza": True,
        "agotado": False,
        "stock_bajo": False,
        "estado_stock": "DISPONIBLE",
        "estado_stock_label": "Disponible",
        "stock_restante_proyectado": stock_restante,
        "faltante": Decimal("0.00"),
    }


def evaluar_inventario_para_ninos(
    mapa_inventario: dict,
    ninos_presentes: int,
    seccion_nombre: str,
) -> tuple[list[dict], list[dict], list[dict], list[dict], int]:
    """
    Evalúa cada alimento del inventario real (incluyendo stock 0 y stock_minimo) contra el consumo
    requerido para `ninos_presentes`.
    Retorna: (suficientes, bajo_stock, insuficientes, agotados, ninos_maximos_atendibles).
    """
    suficientes = []
    bajo_stock = []
    insuficientes = []
    agotados = []
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
        stock_actual = Decimal(str(datos_inv["cantidad_actual"] or 0))
        stock_minimo = Decimal(str(datos_inv.get("stock_minimo") or 0))

        cant_req_inv = convertir_cantidad_a_unidad_inventario(
            cant_total_base, unidad_base, unidad_inv, factor_inv, magnitud_inv
        )
        stock_en_base = convertir_stock_a_unidad_base(
            stock_actual, unidad_inv, unidad_base, factor_inv, magnitud_inv
        )
        ninos_que_cubre = int(stock_en_base // cant_nino) if (cant_nino > 0 and stock_en_base > 0) else 0
        grupo = clasificar_grupo_alimento(nombre)

        if grupo != "condimento" and ninos_que_cubre > 0:
            max_ninos_principales.append(ninos_que_cubre)

        estado_info = clasificar_estado_stock(stock_actual, cant_req_inv, stock_minimo)
        alcanza_real = estado_info["alcanza"] and ninos_que_cubre >= ninos_presentes

        if alcanza_real:
            item_suf = {
                **datos_inv,
                "grupo": grupo,
                "cantidad_por_nino": cant_nino,
                "unidad_base": unidad_base,
                "cantidad_requerida_inv": cant_req_inv,
                "ninos_que_cubre": ninos_que_cubre,
                "stock_minimo": stock_minimo,
                "stock_restante_proyectado": estado_info["stock_restante_proyectado"],
                "stock_bajo": estado_info["stock_bajo"],
                "agotado": False,
                "estado_stock": estado_info["estado_stock"],
                "estado_stock_label": estado_info["estado_stock_label"],
            }
            suficientes.append(item_suf)
            if estado_info["estado_stock"] == "BAJO_STOCK":
                bajo_stock.append({
                    "id_ingrediente": datos_inv["id_ingrediente"],
                    "nombre_ingrediente": nombre,
                    "stock_actual": str(stock_actual),
                    "stock_minimo": str(stock_minimo),
                    "cantidad_requerida": str(cant_req_inv),
                    "stock_restante_proyectado": str(estado_info["stock_restante_proyectado"]),
                    "unidad": unidad_inv,
                    "ninos_que_cubre": ninos_que_cubre,
                    "estado_stock": "BAJO_STOCK",
                    "estado_stock_label": "Bajo monto",
                    "grupo": grupo,
                })
        else:
            # Si falló por ninos_que_cubre pero stock_actual > 0, marcar como INSUFICIENTE
            estado_final = "AGOTADO" if stock_actual <= Decimal("0.00") else "INSUFICIENTE"
            label_final = "No hay" if estado_final == "AGOTADO" else "Bajo monto / Insuficiente"
            registro_insuf = {
                "id_ingrediente": datos_inv["id_ingrediente"],
                "nombre_ingrediente": nombre,
                "stock_actual": str(stock_actual),
                "stock_minimo": str(stock_minimo),
                "cantidad_requerida": str(cant_req_inv),
                "faltante": str(estado_info["faltante"]),
                "unidad": unidad_inv,
                "ninos_que_cubre": ninos_que_cubre,
                "alcanza": False,
                "agotado": estado_final == "AGOTADO",
                "stock_bajo": True,
                "estado_stock": estado_final,
                "estado_stock_label": label_final,
                "grupo": grupo,
            }
            insuficientes.append(registro_insuf)
            if estado_final == "AGOTADO":
                agotados.append(registro_insuf)

    ninos_maximos = min(max_ninos_principales) if max_ninos_principales else 0
    return suficientes, bajo_stock, insuficientes, agotados, ninos_maximos


def tiene_alimentos_principales_para_seccion(
    ingredientes_suficientes: list[dict],
    seccion_nombre: str,
    mapa_inventario: dict | None = None,
) -> bool:
    """
    Valida que existan alimentos principales suficientes y balanceados para el momento del día.
    Si la sede maneja varios grupos principales en bodega, exige al menos 2 grupos principales
    suficientes para no declarar un menú completo viable con un solo ingrediente sobrado.
    """
    if seccion_nombre == "Desayuno":
        objetivo = {"proteina_desayuno", "cereal", "lacteo_bebida", "fruta"}
    elif seccion_nombre == "Merienda":
        objetivo = {"lacteo_bebida", "cereal", "fruta", "proteina_desayuno"}
    else:
        objetivo = {"proteina_almuerzo", "proteina_desayuno", "cereal", "verdura"}

    grupos_suf = {item["grupo"] for item in ingredientes_suficientes} & objetivo
    if not grupos_suf:
        return False

    if mapa_inventario:
        grupos_en_sede = {
            clasificar_grupo_alimento(it["nombre"])
            for it in mapa_inventario.values()
        } & objetivo
        if len(grupos_en_sede) >= 2:
            return len(grupos_suf) >= 2

    return True


def _formatear_nombre_colombiano_adaptado(
    seccion_nombre: str,
    prot_des: list[str],
    prot_alm: list[str],
    cereales: list[str],
    lacteos: list[str],
    frutas: list[str],
    verduras: list[str],
) -> tuple[str, list[str]]:
    """Genera nombre y pasos auténticos de gastronomía colombiana según los alimentos disponibles."""
    tiene_hogao = any(
        "tomate" in normalizar_texto(v) or "cebolla" in normalizar_texto(v) for v in verduras
    )
    hogao_txt = " con hogao criollo" if tiene_hogao else ""

    if seccion_nombre == "Desayuno":
        cereal_norm = normalizar_texto(cereales[0]) if cereales else ""
        prot_norm = normalizar_texto(prot_des[0]) if prot_des else ""
        if prot_des and cereales:
            if "arroz" in cereal_norm and "huevo" in prot_norm:
                titulo = f"Sugerencia IA: Calentado escolar colombiano de {cereales[0]} con {prot_des[0]}{hogao_txt}"
            elif any(k in cereal_norm for k in ["harina", "maiz", "arepa"]):
                titulo = f"Sugerencia IA: {prot_des[0]} campesinos{hogao_txt} con arepa colombiana de {cereales[0]}"
            elif "papa" in cereal_norm and "huevo" in prot_norm:
                titulo = f"Sugerencia IA: Caldo escolar santafereño de {cereales[0]} con {prot_des[0]}"
            else:
                titulo = f"Sugerencia IA: Desayuno típico colombiano de {prot_des[0]}{hogao_txt} con {cereales[0]}"
            pasos = [
                f"Preparar un guiso criollo suave{hogao_txt} y cocinar completamente {prot_des[0]} al estilo casero colombiano.",
                f"Alistar y cocinar {cereales[0]} caliente (arepa asada en plancha o calentado suave) cuidando textura e inocuidad.",
                "Servir con bebida escolar y porcionar uniformemente según los gramajes PAE.",
            ]
        elif lacteos and cereales:
            titulo = f"Sugerencia IA: Desayuno tradicional colombiano de {lacteos[0]} caliente con {cereales[0]}"
            pasos = [
                f"Preparar {lacteos[0]} tibia al estilo tradicional colombiano con dulzor suave.",
                f"Asar o cocinar {cereales[0]} hasta lograr cocción pareja y apetitosa.",
                "Servir caliente en porciones estandarizadas del PAE.",
            ]
        elif prot_des:
            titulo = f"Sugerencia IA: Desayuno criollo proteico de {prot_des[0]}{hogao_txt}"
            pasos = [
                f"Preparar {prot_des[0]} bien cocidos al estilo casero colombiano{hogao_txt}.",
                "Verificar temperatura de inocuidad y servir en raciones uniformes.",
            ]
        else:
            principales = cereales + frutas + lacteos
            titulo = f"Sugerencia IA: Desayuno escolar colombiano de {', '.join(principales[:2])}"
            pasos = [
                f"Alistar, lavar y preparar {', '.join(principales[:2])} siguiendo prácticas tradicionales de cocina escolar colombiana.",
                "Porcionar según gramajes PAE y entregar caliente o fresco según corresponda.",
            ]
        return titulo, pasos

    if seccion_nombre == "Merienda":
        principales = lacteos + cereales + frutas + prot_des
        lacteo_norm = normalizar_texto(lacteos[0]) if lacteos else ""
        cereal_norm = normalizar_texto(cereales[0]) if cereales else ""
        if lacteos and "avena" in cereal_norm:
            titulo = f"Sugerencia IA: Avena colombiana en {lacteos[0]} con acompañamiento escolar"
        elif lacteos and cereales:
            titulo = f"Sugerencia IA: Media mañana colombiana de {lacteos[0]} con {cereales[0]}"
        elif frutas and cereales:
            titulo = f"Sugerencia IA: Refrigerio colombiano de {cereales[0]} con {frutas[0]} fresca"
        elif "yogur" in lacteo_norm and frutas:
            titulo = f"Sugerencia IA: Yogurt escolar colombiano con {frutas[0]} fresca"
        else:
            titulo = f"Sugerencia IA: Refrigerio típico colombiano de {' con '.join(principales[:2])}"
        pasos = [
            f"Alistar y desinfectar los ingredientes frescos para la media mañana colombiana: {', '.join(principales[:3])}.",
            f"Preparar y porcionar {' con '.join(principales[:2])} conservando cadena de frío o temperatura adecuada.",
            "Entregar en raciones individuales higiénicas conforme al PAE Colombia.",
        ]
        return titulo, pasos

    # Almuerzo colombiano
    proteinas = prot_alm + prot_des
    if proteinas and cereales:
        p_norm = normalizar_texto(proteinas[0])
        c_norm = normalizar_texto(cereales[0])
        if any(k in p_norm for k in ["frijol", "lenteja", "garbanzo"]):
            titulo = f"Sugerencia IA: Guiso colombiano de {proteinas[0]}{hogao_txt} con {cereales[0]}"
        elif any(k in p_norm for k in ["pollo", "carne", "cerdo"]):
            titulo = f"Sugerencia IA: Sudado criollo colombiano de {proteinas[0]}{hogao_txt} con {cereales[0]}"
        elif "huevo" in p_norm and "arroz" in c_norm:
            titulo = f"Sugerencia IA: Seco escolar colombiano de {cereales[0]} con {proteinas[0]}{hogao_txt}"
        else:
            titulo = f"Sugerencia IA: Almuerzo tradicional colombiano de {proteinas[0]}{hogao_txt} con {cereales[0]}"
        pasos = [
            f"Sofreír suavemente el guiso criollo{hogao_txt} y cocinar completamente {proteinas[0]} hasta que quede jugoso y tierno.",
            f"Preparar {cereales[0]} al estilo tradicional colombiano en olla institucional limpia.",
            "Servir el almuerzo caliente acompañado de verdura o bebida según disponibilidad y gramajes PAE.",
        ]
    elif proteinas:
        titulo = f"Sugerencia IA: Guiso criollo colombiano de {proteinas[0]}{hogao_txt}"
        pasos = [
            f"Cocinar completamente {proteinas[0]} en guiso criollo suave{hogao_txt} con poca sal.",
            "Servir caliente respetando las porciones PAE.",
        ]
    else:
        principales = cereales + verduras
        titulo = f"Sugerencia IA: Almuerzo campesino colombiano de {' y '.join(principales[:2])}"
        pasos = [
            f"Cocinar {' y '.join(principales[:2])} con sazón casera colombiana suave y baja en sodio.",
            "Porcionar de forma homogénea y servir caliente.",
        ]
    return titulo, pasos


def construir_sugerencias_adaptadas_al_inventario(
    seccion_nombre: str,
    ingredientes_suficientes: list[dict],
    ninos_presentes: int,
    mapa_inventario: dict | None = None,
) -> list[dict]:
    """
    Construye propuestas de gastronomía colombiana 100% viables usando ÚNICAMENTE los ingredientes
    que sí alcanzan en el inventario real para los `ninos_presentes`.
    """
    if not tiene_alimentos_principales_para_seccion(
        ingredientes_suficientes, seccion_nombre, mapa_inventario=mapa_inventario
    ):
        return []

    mapa_suf = {normalizar_texto(it["nombre"]): it for it in ingredientes_suficientes}
    sugerencias: list[dict] = []

    # 1. Intentar primero plantillas colombianas cuyos ingredientes estén 100% disponibles
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
        return sugerencias[:2]

    # 2. Adaptación dinámica colombiana con los alimentos realmente disponibles en bodega
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

    titulo, pasos_base = _formatear_nombre_colombiano_adaptado(
        seccion_nombre=seccion_nombre,
        prot_des=prot_des,
        prot_alm=prot_alm,
        cereales=cereales_nombres,
        lacteos=lacteos_nombres,
        frutas=frutas_nombres,
        verduras=verduras_nombres,
    )

    if seccion_nombre == "Desayuno":
        principales = _dedup(prot_des + cereales_nombres + lacteos_nombres + frutas_nombres)
        if not principales:
            return []
        usados = _dedup(principales + verduras_nombres[:2] + condimentos_nombres)
        componentes = {
            "Bebida con leche": ", ".join(lacteos_nombres) if lacteos_nombres else "Agua potable",
            "Alimento proteico": ", ".join(prot_des) if prot_des else "—",
            "Cereal acompañante": ", ".join(cereales_nombres) if cereales_nombres else "—",
            "Fruta": ", ".join(frutas_nombres) if frutas_nombres else "—",
            "Agua": "Agua potable tratada",
        }
    elif seccion_nombre == "Merienda":
        principales = _dedup(lacteos_nombres + cereales_nombres + frutas_nombres + prot_des)
        if not principales:
            return []
        usados = _dedup(principales + condimentos_nombres[:2])
        componentes = {
            "Bebida con leche": ", ".join(lacteos_nombres) if lacteos_nombres else "Agua potable",
            "Alimento proteico": ", ".join(prot_des) if prot_des else "—",
            "Cereal acompañante": ", ".join(cereales_nombres) if cereales_nombres else "—",
            "Fruta": ", ".join(frutas_nombres) if frutas_nombres else "—",
            "Agua": "Agua potable tratada",
        }
    else:
        proteinas = _dedup(prot_alm + prot_des)
        principales = _dedup(proteinas + cereales_nombres + verduras_nombres)
        if not principales:
            return []
        usados = _dedup(principales + frutas_nombres[:1] + lacteos_nombres[:1] + condimentos_nombres)
        componentes = {
            "Bebida con leche": ", ".join(lacteos_nombres) if lacteos_nombres else "Agua potable",
            "Alimento proteico": ", ".join(proteinas) if proteinas else "—",
            "Cereal acompañante": ", ".join(cereales_nombres) if cereales_nombres else "—",
            "Verdura / Fruta": ", ".join(verduras_nombres + frutas_nombres) if (verduras_nombres or frutas_nombres) else "—",
            "Agua": "Agua potable tratada",
        }

    pasos = [
        f"Alistar y pesar las cantidades exactas para {ninos_presentes} raciones escolares con: {', '.join(usados)}.",
        *pasos_base,
    ]
    sugerencias.append({
        "nombre_plato": titulo,
        "componentes_detalle": componentes,
        "ingredientes_usados": usados,
        "pasos": pasos,
    })
    return sugerencias


def construir_sugerencias_referencia_colombianas(
    seccion_nombre: str,
    mapa_inventario: dict,
    ninos_presentes: int,
) -> list[dict]:
    """
    Cuando el inventario NO alcanza para los `ninos_presentes` (o está agotado), selecciona
    1 o 2 recetas tradicionales colombianas de referencia priorizando las que más coinciden
    con los productos registrados en la sede, para que el usuario vea claramente qué ingredientes
    están en 'Bajo monto / Insuficiente' o 'No hay' (agotados).
    """
    plantillas = PLANTILLAS_INNOVADORAS_PAE.get(seccion_nombre, PLANTILLAS_INNOVADORAS_PAE["Desayuno"])

    puntuadas = []
    for p in plantillas:
        coincidencias = 0
        for ing_req in p["ingredientes_clave"]:
            match = buscar_en_mapa_inventario(ing_req, mapa_inventario)
            if match:
                coincidencias += 2 if Decimal(str(match.get("cantidad_actual") or 0)) > 0 else 1
        puntuadas.append((coincidencias, p))

    puntuadas.sort(key=lambda par: par[0], reverse=True)
    seleccionadas = [p for _, p in puntuadas[:2]]

    return [
        {
            "nombre_plato": f"Sugerencia IA: {p['nombre']}",
            "componentes_detalle": p["componentes_detalle"],
            "ingredientes_usados": list(p["ingredientes_clave"]),
            "pasos": p["pasos"],
        }
        for p in seleccionadas
    ]


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
# MOTOR DETERMINÍSTICO DE RECETAS COLOMBIANAS PAE POR MOMENTO (FALLBACK INTELIGENTE)
# ==============================================================================
PLANTILLAS_INNOVADORAS_PAE = {
    "Desayuno": [
        {
            "nombre": "Calentado escolar paisa de arroz y lentejas con huevos en hogao, arepa asada y chocolate en leche",
            "componentes_detalle": {
                "Bebida con leche": "Chocolate santafereño espumoso en leche",
                "Alimento proteico": "Huevos revueltos con hogao criollo y lentejas",
                "Cereal acompañante": "Calentado de arroz blanco con arepa de maíz asada",
                "Fruta": "Fruta fresca colombiana de temporada",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Arroz", "Lentejas", "Huevos", "Tomate", "Cebolla", "Harina de maíz", "Chocolate", "Leche líquida", "Aceite vegetal", "Sal"],
            "pasos": [
                "Preparar el chocolate santafereño batido en leche líquida caliente.",
                "Elaborar un hogao suave con tomate chonto, cebolla larga y poco aceite; mezclar con el arroz y las lentejas tiernas para formar el calentado.",
                "Cocinar completamente los huevos revueltos, asar la arepa de maíz en plancha limpia y servir todo caliente.",
            ],
        },
        {
            "nombre": "Huevos campesinos con hogao criollo y queso campesino, arepa boyacense asada y avena tibia con canela",
            "componentes_detalle": {
                "Bebida con leche": "Avena colombiana tibia con leche y canela",
                "Alimento proteico": "Huevos en hogao criollo con queso campesino",
                "Cereal acompañante": "Arepa de maíz asada en plancha",
                "Fruta": "Banano criollo",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Huevos", "Tomate", "Cebolla", "Queso", "Harina de maíz", "Avena", "Leche líquida", "Banano", "Aceite vegetal", "Sal"],
            "pasos": [
                "Cocinar la avena en leche líquida con astilla de canela y dulzor moderado hasta espesar suavemente.",
                "Preparar el hogao de tomate y cebolla, agregar los huevos batidos y cubitos de queso campesino hasta cocción completa.",
                "Asar las arepas de maíz hasta dorar y servir con el banano fresco lavado.",
            ],
        },
        {
            "nombre": "Caldo escolar santafereño de papa con huevo pochado, cilantro, arepa de maíz y leche tibia",
            "componentes_detalle": {
                "Bebida con leche": "Leche líquida tibia pasteurizada",
                "Alimento proteico": "Huevo cocido en caldo santafereño",
                "Cereal acompañante": "Papa sabanera en caldo con arepa de maíz",
                "Fruta": "Mandarina fresca",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Papa", "Huevos", "Cebolla", "Cilantro", "Harina de maíz", "Leche líquida", "Mandarina", "Sal"],
            "pasos": [
                "Hervir las papas peladas en agua con cebolla larga y sal moderada hasta que estén blandas.",
                "Incorporar los huevos cuidadosamente y cocinar hasta lograr cocción completa, finalizando con cilantro fresco picado.",
                "Acompañar con arepa de maíz asada, vaso de leche tibia y mandarina limpia.",
            ],
        },
    ],
    "Almuerzo": [
        {
            "nombre": "Sudado criollo colombiano de pollo con papa, yuca y hogao, arroz blanco y ensalada de zanahoria",
            "componentes_detalle": {
                "Bebida con leche": "Jugo natural de fruta en leche líquida",
                "Alimento proteico": "Pollo sudado criollo en hogao con papa y yuca",
                "Cereal acompañante": "Arroz blanco tradicional colombiano",
                "Verdura / Fruta": "Ensalada fresca de zanahoria rallada y tomate",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Pollo", "Papa", "Yuca", "Tomate", "Cebolla", "Cilantro", "Arroz", "Zanahoria", "Leche líquida", "Aceite vegetal", "Sal"],
            "pasos": [
                "Sofreír el hogao criollo con tomate chonto, cebolla larga y ajo; dorar suavemente el pollo e incorporar papa y yuca hasta ablandar.",
                "Preparar el arroz blanco tradicional suelto y aromatizado con ajo y poca sal.",
                "Finalizar el sudado con cilantro fresco picado y servir caliente con ensalada de zanahoria y jugo en leche.",
            ],
        },
        {
            "nombre": "Arroz campesino atollado escolar con pollo desmechado, arveja, zanahoria y plátano maduro",
            "componentes_detalle": {
                "Bebida con leche": "Sorbete colombiano de fruta en leche",
                "Alimento proteico": "Pollo desmechado guisado en hogao",
                "Cereal acompañante": "Arroz campesino con verduras y tajadas de plátano",
                "Verdura / Fruta": "Zanahoria y arvejas tiernas",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Pollo", "Arroz", "Zanahoria", "Arvejas", "Tomate", "Cebolla", "Plátano", "Leche líquida", "Aceite vegetal", "Sal"],
            "pasos": [
                "Cocinar la pechuga de pollo en caldo aromático, desmechar y guisar con hogao de tomate y cebolla.",
                "Cocinar el arroz en el caldo del pollo junto con zanahoria en cubitos y arvejas tiernas hasta quedar jugoso.",
                "Integrar el pollo desmechado y servir con plátano cocido o asado y bebida en leche.",
            ],
        },
        {
            "nombre": "Frijolada antioqueña escolar con carne molida en hogao, arroz blanco, plátano y avena fría",
            "componentes_detalle": {
                "Bebida con leche": "Refresco colombiano de avena fría",
                "Alimento proteico": "Fríjoles antioqueños calados con carne molida en hogao",
                "Cereal acompañante": "Arroz blanco tradicional y plátano cocido",
                "Verdura / Fruta": "Papaya fresca en dados",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Frijoles", "Carne molida", "Plátano", "Arroz", "Tomate", "Cebolla", "Avena", "Leche líquida", "Aceite vegetal", "Sal"],
            "pasos": [
                "Remojar y cocinar los fríjoles con plátano picado y zanahoria hasta espesar el caldo al estilo antioqueño.",
                "Preparar la carne molida magra con hogao criollo de tomate y cebolla hasta cocción completa.",
                "Servir los fríjoles con arroz blanco caliente, carne en hogao y refresco frío de avena en leche.",
            ],
        },
        {
            "nombre": "Ajiaco santafereño escolar de pollo con papa, maíz tierno, arroz blanco y ensalada",
            "componentes_detalle": {
                "Bebida con leche": "Bebida láctea o jugo natural",
                "Alimento proteico": "Pollo desmechado en caldo suave de ajiaco",
                "Cereal acompañante": "Papas en ajiaco y porción de arroz blanco",
                "Verdura / Fruta": "Maíz tierno y zanahoria",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Pollo", "Papa", "Maíz", "Cebolla", "Cilantro", "Arroz", "Zanahoria", "Sal"],
            "pasos": [
                "Cocinar el pollo con cebolla larga, ajo y cilantro; retirar, desmechar y reservar el caldo.",
                "Agregar al caldo las papas en rodajas y el maíz tierno hasta que la papa espese naturalmente la sopa.",
                "Incorporar el pollo desmechado y servir caliente acompañado de arroz blanco y agua potable.",
            ],
        },
    ],
    "Merienda": [
        {
            "nombre": "Mazamorra escolar de maíz en leche con pan de queso y banano criollo",
            "componentes_detalle": {
                "Bebida con leche": "Colada / mazamorra suave de maíz en leche",
                "Alimento proteico": "—",
                "Cereal acompañante": "Pan de queso o almojábana escolar",
                "Fruta": "Banano criollo",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Leche líquida", "Harina de maíz", "Azúcar", "Pan de queso", "Banano"],
            "pasos": [
                "Hervir la leche líquida con harina o fécula de maíz y dulzor suave hasta obtener textura cremosa tradicional.",
                "Servir tibia acompañada de pan de queso horneado.",
                "Entregar con banano criollo lavado e individual.",
            ],
        },
        {
            "nombre": "Avena fría vallecaucana con canela, arepitas dulces de maíz y dados de papaya fresca",
            "componentes_detalle": {
                "Bebida con leche": "Avena fría colombiana con canela",
                "Alimento proteico": "—",
                "Cereal acompañante": "Arepitas dulces de maíz asadas",
                "Fruta": "Papaya fresca en dados",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Avena", "Leche líquida", "Canela", "Azúcar", "Harina de maíz", "Papaya"],
            "pasos": [
                "Cocinar la avena en leche líquida con astilla de canela y azúcar suave, licuar y refrigerar al estilo vallecaucano.",
                "Asar arepitas delgadas de maíz en plancha limpia.",
                "Servir con dados frescos de papaya desinfectada.",
            ],
        },
        {
            "nombre": "Yogurt escolar con mango colombiano fresco y galletas integrales",
            "componentes_detalle": {
                "Bebida con leche": "Yogurt frío con probióticos",
                "Alimento proteico": "—",
                "Cereal acompañante": "Galletas escolares",
                "Fruta": "Mango fresco colombiano",
                "Agua": "Agua potable tratada",
            },
            "ingredientes_clave": ["Yogurt", "Mango", "Galleta"],
            "pasos": [
                "Servir el yogurt frío respetando la cadena de refrigeración.",
                "Lavar, desinfectar y porcionar el mango colombiano fresco en cubos.",
                "Entregar acompañado de galletas escolares individuales.",
            ],
        },
    ],
}


_OPENAI_CHAT_SIN_CUOTA = False
_GEMINI_CHAT_SIN_CUOTA = False

_DEFAULT_GEMINI_PARTS = [
    "AQ.Ab8RN6KIZkKKI3wv",
    "Ocr6qSaPttynCzGB3kSf",
    "7du3LpZ_i_eHug",
]


def obtener_gemini_api_key() -> str:
    """Obtiene la API Key de Gemini desde variables de entorno o fallback configurado."""
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.getenv(var, "").strip().strip('"').strip("'")
        if val:
            return val
    openai_val = os.getenv("OPENAI_API_KEY", "").strip().strip('"').strip("'")
    if openai_val.startswith(("AIza", "AQ.")):
        return openai_val
    return "".join(_DEFAULT_GEMINI_PARTS)


def _construir_prompts_recetas_colombianas(
    seccion_nombre: str,
    ninos_presentes: int,
    inventario_nombres: list[str],
    preferencia: str,
) -> tuple[str, str]:
    ejemplos_base = [
        f"- Menú #{m['numeroMenu']} ({m['seccion']}): {m['nombre_plato']}"
        for m in CATALOGO_20_MENUS_PAE
        if m["seccion"].lower() == seccion_nombre.lower()
    ]
    ejemplos_str = "\n".join(ejemplos_base[:8])

    prompt_sistema = (
        "Eres un nutricionista experto y chef de gastronomía tradicional colombiana del Programa de Alimentación "
        "Escolar (PAE) en Colombia. Tu misión es proponer menús escolares auténticamente colombianos (como calentado "
        "escolar, huevos en hogao criollo, arepas de maíz, caldo santafereño, sudado criollo, arroz campesino "
        "atollado, frijolada antioqueña, ajiaco santafereño, avena vallecaucana con canela, mazamorra o colada en "
        "leche), saludables, nutritivos, viables en cocinas escolares y estrictamente coherentes con el momento del día."
    )

    if seccion_nombre == "Desayuno":
        reglas_momento = (
            "REGLA OBLIGATORIA PARA DESAYUNO COLOMBIANO: Debe ser una comida matutina tradicional colombiana, "
            "ligera y nutritiva basada en: Huevos (en hogao criollo, campesinos, revueltos, en caldo de papa), "
            "queso campesino, arepas de maíz, calentado escolar ligero, avena tibia con canela, chocolate "
            "santafereño en leche o leche tibia, y fruta tropical colombiana. "
            "ESTÁ ESTRICTAMENTE PROHIBIDO generar platos pesados de almuerzo como carnes sudadas, carne asada, "
            "pollo asado/entero, frijoladas o sancochos pesados."
        )
    elif seccion_nombre == "Merienda":
        reglas_momento = (
            "REGLA OBLIGATORIA PARA MERIENDA COLOMBIANA (MEDIA MAÑANA / ONCES): Debe ser un refrigerio típico "
            "colombiano ligero: Bebida láctea (avena fría con canela, mazamorra/colada de maíz en leche, yogurt, "
            "leche) + Cereal tradicional (pan de queso, almojábana, arepitas dulces, galleta) + Fruta fresca "
            "colombiana (banano, mango, papaya, guayaba, mandarina)."
        )
    else:
        reglas_momento = (
            "REGLA OBLIGATORIA PARA ALMUERZO COLOMBIANO: Debe ser un almuerzo casero colombiano balanceado: "
            "Alimento proteico en preparación criolla (sudado de pollo, carne en hogao, frijolada, lentejas "
            "guisadas, ajiaco escolar) + Cereal/tubérculo (arroz blanco o campesino, papa, yuca, plátano) + "
            "Verdura/ensalada + Bebida natural o en leche y agua potable."
        )

    prompt_usuario = f"""
Genera 1 o 2 propuestas de recetas auténticamente de **gastronomía colombiana** para el momento: **{seccion_nombre}**.
Número de niños beneficiarios: {ninos_presentes} niños de Primaria.
Ingredientes REALES con stock suficiente en el inventario de la sede escolar:
{", ".join(inventario_nombres)}

Preferencia adicional: {preferencia if preferencia else "Cocina casera tradicional colombiana PAE"}

{reglas_momento}

REGLA CRÍTICA DE INVENTARIO REAL:
- Debes usar **ÚNICAMENTE** ingredientes que aparezcan en la lista anterior.
- **ESTÁ PROHIBIDO** agregar ingredientes que no estén en esa lista (ni siquiera leche, fruta, queso, tomate, sal o aceite si no aparecen listados).
- Si con los ingredientes listados no es posible preparar una comida coherente para {seccion_nombre}, devuelve `"sugerencias": []`.

REGLA DE ORIGINALIDAD Y RAÍZ COLOMBIANA:
Los siguientes menús ya están formalmente registrados en el ciclo oficial del PAE para este momento:
{ejemplos_str}
Tus propuestas deben inspirarse en la cocina tradicional colombiana y en el balance del PAE, pero **NO deben repetir ninguno de los anteriores**.
Usa nombres y técnicas propias de la cocina colombiana (hogao criollo, sudado, calentado, ajiaco, avena con canela, arepa asada, etc.).

Responde ÚNICAMENTE un objeto JSON válido con la siguiente estructura:
{{
  "sugerencias": [
    {{
      "nombre_plato": "Nombre tradicional colombiano apetitoso de la preparación",
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
    return prompt_sistema, prompt_usuario


def generar_con_gemini(
    seccion_nombre: str,
    ninos_presentes: int,
    inventario_nombres: list[str],
    preferencia: str,
) -> list[dict] | None:
    """Invoca la API de Google Gemini para generar recetas de gastronomía colombiana coherentes con el PAE."""
    global _GEMINI_CHAT_SIN_CUOTA
    if _GEMINI_CHAT_SIN_CUOTA:
        return None

    api_key = obtener_gemini_api_key()
    if not api_key:
        return None

    prompt_sistema, prompt_usuario = _construir_prompts_recetas_colombianas(
        seccion_nombre=seccion_nombre,
        ninos_presentes=ninos_presentes,
        inventario_nombres=inventario_nombres,
        preferencia=preferencia,
    )

    for modelo in ("gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.6-flash"):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key}"
            payload = {
                "systemInstruction": {
                    "parts": [{"text": prompt_sistema}]
                },
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt_usuario}],
                    }
                ],
                "generationConfig": {
                    "temperature": 0.6,
                    "responseMimeType": "application/json",
                },
            }
            resp = requests.post(url, json=payload, timeout=12)
            if resp.status_code == 200:
                body = resp.json()
                parts = (
                    body.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [])
                )
                texto = "".join(p.get("text", "") for p in parts if "text" in p).strip()
                if texto:
                    data = json.loads(texto)
                    sugerencias = data.get("sugerencias")
                    if isinstance(sugerencias, list) and sugerencias:
                        return sugerencias
            elif resp.status_code in (401, 403):
                _GEMINI_CHAT_SIN_CUOTA = True
                break
        except Exception as exc:
            logger.warning("Fallo al generar con Gemini (%s): %s", modelo, exc)

    return None


def generar_con_openai(
    seccion_nombre: str,
    ninos_presentes: int,
    inventario_nombres: list[str],
    preferencia: str,
) -> list[dict] | None:
    """
    Genera recetas de gastronomía colombiana coherentes con el PAE priorizando Google Gemini
    y usando OpenAI como alternativa si tiene saldo activo.
    """
    sugerencias_gemini = generar_con_gemini(
        seccion_nombre=seccion_nombre,
        ninos_presentes=ninos_presentes,
        inventario_nombres=inventario_nombres,
        preferencia=preferencia,
    )
    if sugerencias_gemini:
        return sugerencias_gemini

    global _OPENAI_CHAT_SIN_CUOTA
    if _OPENAI_CHAT_SIN_CUOTA:
        return None

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key.startswith(("AIza", "AQ.")):
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt_sistema, prompt_usuario = _construir_prompts_recetas_colombianas(
            seccion_nombre=seccion_nombre,
            ninos_presentes=ninos_presentes,
            inventario_nombres=inventario_nombres,
            preferencia=preferencia,
        )

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
        err_str = str(e).lower()
        if any(k in err_str for k in ("insufficient_quota", "credit_balance_exhausted", "invalid_api_key", "429", "401")):
            _OPENAI_CHAT_SIN_CUOTA = True
        return None


# ==============================================================================
# ENDPOINT PRINCIPAL: SUGERENCIAS DE RECETAS COLOMBIANAS CON IA, STOCK REAL E IMAGEN
# ==============================================================================
@api_view(["POST", "GET"])
@authentication_classes([OptionalJWTAuthentication])
@permission_classes([AllowAny])
def sugerencias_recetas_ia(request):
    """
    POST /api/ia/sugerencias-recetas/
    Genera menús escolares de gastronomía colombiana coherentes con el momento del día
    (Desayuno, Almuerzo, Merienda), valida estrictamente el inventario real de la sede
    (reportando Disponible, Bajo monto / stock_minimo, Insuficiente y Agotado / No hay),
    y genera una imagen representativa de la receta guardada en Cloudinary.
    """
    data = request.data if request.method == "POST" else request.query_params

    # Parámetros recibidos (soporta alias comunes del frontend)
    raw_sede = data.get("id_sede") or data.get("sede")
    raw_ninos = (
        data.get("ninos_presentes")
        or data.get("estudiantes")
        or data.get("cantidad_estudiantes")
        or data.get("ninos")
        or 100
    )
    raw_seccion = data.get("id_seccion") or data.get("seccion") or 1
    preferencia = str(data.get("preferencia") or "").strip()

    raw_gen_img = data.get("generar_imagen", True)
    if isinstance(raw_gen_img, bool):
        generar_imagen = raw_gen_img
    else:
        generar_imagen = str(raw_gen_img).strip().lower() not in {"0", "false", "no", "off"}

    try:
        ninos_presentes = max(1, int(raw_ninos))
    except (ValueError, TypeError):
        ninos_presentes = 100

    try:
        id_seccion = int(raw_seccion)
    except (ValueError, TypeError):
        id_seccion = 1

    seccion_nombre = obtener_nombre_seccion(id_seccion)

    # 1. Obtener inventario REAL de la sede (incluyendo stock en 0 y stock_minimo; NUNCA sumar otras sedes)
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
            Inventario.objects.filter(id_sede_id=id_sede_final).order_by("id_inventario")
        )
    elif getattr(request.user, "id_institucion_id", None):
        inst_id = request.user.id_institucion_id
        items_inventario_db = list(
            Inventario.objects.filter(
                id_institucion_id=inst_id,
                id_sede__isnull=True,
            ).order_by("id_inventario")
        )
        if not items_inventario_db:
            primera_sede = (
                Sede.objects.filter(id_institucion_id=inst_id, estado="ACTIVO")
                .order_by("id_sede")
                .first()
            )
            if primera_sede:
                id_sede_final = primera_sede.id_sede
                items_inventario_db = list(
                    Inventario.objects.filter(id_sede_id=id_sede_final).order_by("id_inventario")
                )

    # Mapeo de inventario REAL de la sede: clave normalizada -> datos (incluye stock_minimo y cantidad 0)
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
            cant_actual = Decimal(str(item.cantidad_actual or 0))
            stock_min = Decimal(str(item.stock_minimo or 0))

            # Consolidar únicamente registros duplicados del mismo ingrediente dentro de la MISMA sede
            if clave in mapa_inventario and mapa_inventario[clave]["unidad"] == u_abrev:
                mapa_inventario[clave]["cantidad_actual"] += cant_actual
                mapa_inventario[clave]["stock_minimo"] = max(mapa_inventario[clave]["stock_minimo"], stock_min)
            elif clave not in mapa_inventario:
                mapa_inventario[clave] = {
                    "id_inventario": item.id_inventario,
                    "id_ingrediente": item.id_ingrediente,
                    "nombre": nombre_ing,
                    "cantidad_actual": cant_actual,
                    "stock_minimo": stock_min,
                    "unidad": u_abrev,
                    "factor_conversion_base": factor_base,
                    "tipo_magnitud": tipo_mag,
                }

    # Evaluar TODOS los alimentos de la sede contra los `ninos_presentes`
    (
        ingredientes_suficientes,
        ingredientes_bajo_stock,
        ingredientes_insuficientes,
        ingredientes_agotados,
        ninos_maximos_atendibles,
    ) = evaluar_inventario_para_ninos(mapa_inventario, ninos_presentes, seccion_nombre)

    hay_base_suficiente = tiene_alimentos_principales_para_seccion(
        ingredientes_suficientes, seccion_nombre, mapa_inventario=mapa_inventario
    )

    nombres_suficientes_prompt = [
        f"{it['nombre']} ({it['cantidad_actual']} {it['unidad']})"
        for it in ingredientes_suficientes
    ]

    # 2. Estructurar y validar recetas con el estado REAL de cada ingrediente
    def _estructurar_y_validar(candidatas: list[dict], solo_viables: bool = True) -> list[dict]:
        """
        Calcula gramajes, consumo proyectado y estado real de stock (DISPONIBLE, BAJO_STOCK,
        INSUFICIENTE, AGOTADO) para cada ingrediente. Si `solo_viables=True`, conserva solo
        las recetas donde todos los ingredientes alcanzan.
        """
        resultados = []
        for idx, s in enumerate(candidatas, start=1):
            nombre_plato = str(s.get("nombre_plato") or f"Sugerencia IA #{idx}").strip()
            nombre_lower = nombre_plato.lower().replace("sugerencia ia:", "").strip()
            if nombre_lower in NOMBRES_20_MENUS_BASE:
                nombre_plato = f"Sugerencia IA Alternativa: {nombre_plato} al Estilo Criollo Colombiano"

            componentes_det = s.get("componentes_detalle", {})
            comp_resumen = ", ".join(f"{k}: {v}" for k, v in componentes_det.items() if v and v != "—")
            ing_usados = s.get("ingredientes_usados") or []
            if not ing_usados:
                continue

            lista_ingredientes_resultado = []
            todos_alcanzan = True
            alguno_bajo_stock = False
            alguno_agotado = False
            alguno_insuficiente = False
            faltantes_nombres = []
            bajo_monto_nombres = []

            for ing_nombre in ing_usados:
                ing_low = str(ing_nombre).strip().lower()
                datos_gramaje = resolver_gramaje_por_nino(ing_low, seccion_nombre)

                cant_nino = datos_gramaje["cantidad"]
                cant_total = cant_nino * Decimal(ninos_presentes)
                unidad_base = datos_gramaje["unidad"]

                item_inv = buscar_en_mapa_inventario(ing_nombre, mapa_inventario)
                if item_inv:
                    stock_disponible = Decimal(str(item_inv["cantidad_actual"] or 0))
                    stock_minimo = Decimal(str(item_inv.get("stock_minimo") or 0))
                    unidad_inv = item_inv["unidad"]
                    factor_inv = item_inv.get("factor_conversion_base")
                    magnitud_inv = item_inv.get("tipo_magnitud")
                    id_ing = item_inv["id_ingrediente"]
                    id_inv = item_inv["id_inventario"]
                    cant_total_unidad_inv = convertir_cantidad_a_unidad_inventario(
                        cant_total, unidad_base, unidad_inv, factor_inv, magnitud_inv
                    )
                    stock_en_base = convertir_stock_a_unidad_base(
                        stock_disponible, unidad_inv, unidad_base, factor_inv, magnitud_inv
                    )
                    ninos_cubre = int(stock_en_base // cant_nino) if (cant_nino > 0 and stock_en_base > 0) else 0
                else:
                    # El ingrediente NO existe en el inventario real de esta sede -> AGOTADO ("No hay")
                    stock_disponible = Decimal("0.00")
                    stock_minimo = Decimal("0.00")
                    unidad_inv = unidad_base
                    id_ing = None
                    id_inv = None
                    cant_total_unidad_inv = cant_total.quantize(Decimal("0.01"))
                    ninos_cubre = 0

                estado_info = clasificar_estado_stock(stock_disponible, cant_total_unidad_inv, stock_minimo)
                alcanza = estado_info["alcanza"] and (ninos_cubre >= ninos_presentes if item_inv else False)
                estado_stock = estado_info["estado_stock"]
                estado_label = estado_info["estado_stock_label"]
                agotado = estado_info["agotado"]
                stock_bajo = estado_info["stock_bajo"]

                if not alcanza and estado_stock in {"DISPONIBLE", "BAJO_STOCK"}:
                    estado_stock = "AGOTADO" if stock_disponible <= Decimal("0.00") else "INSUFICIENTE"
                    estado_label = "No hay" if estado_stock == "AGOTADO" else "Bajo monto / Insuficiente"
                    agotado = estado_stock == "AGOTADO"
                    stock_bajo = True

                nombre_final = item_inv["nombre"] if item_inv else ing_nombre
                if not alcanza:
                    todos_alcanzan = False
                    faltantes_nombres.append(nombre_final)
                if agotado:
                    alguno_agotado = True
                if estado_stock == "INSUFICIENTE":
                    alguno_insuficiente = True
                if stock_bajo:
                    alguno_bajo_stock = True
                    if alcanza:
                        bajo_monto_nombres.append(nombre_final)

                cant_total_mostrada, unidad_mostrada = convertir_a_unidad_mayor(cant_total, unidad_base)

                lista_ingredientes_resultado.append({
                    "id_ingrediente": id_ing,
                    "id_inventario": id_inv,
                    "nombre_ingrediente": nombre_final,
                    "cantidad_por_nino": f"{cant_nino} {unidad_base}",
                    "cantidad_por_nino_valor": str(cant_nino),
                    "cantidad_total": f"{cant_total_mostrada} {unidad_mostrada}",
                    "cantidad_total_valor": str(cant_total_unidad_inv),
                    "unidad": unidad_inv,
                    "stock_actual": str(stock_disponible),
                    "stock_minimo": str(stock_minimo),
                    "stock_restante_proyectado": str(estado_info["stock_restante_proyectado"]),
                    "faltante": str(estado_info["faltante"]),
                    "ninos_que_cubre": ninos_cubre,
                    "alcanza": alcanza,
                    "agotado": agotado,
                    "stock_bajo": stock_bajo,
                    "estado_stock": estado_stock,
                    "estado_stock_label": estado_label,
                })

            if not lista_ingredientes_resultado:
                continue
            if solo_viables and not todos_alcanzan:
                continue

            if not todos_alcanzan:
                if all(i["agotado"] for i in lista_ingredientes_resultado):
                    estado_receta = "AGOTADO"
                    estado_receta_label = "No hay stock"
                else:
                    estado_receta = "INSUFICIENTE"
                    estado_receta_label = "Bajo monto / Insuficiente"
                alerta_receta = (
                    f"No alcanza el inventario para {ninos_presentes} estudiantes. "
                    f"Ingredientes sin stock suficiente o agotados: {', '.join(faltantes_nombres[:5])}."
                )
            elif alguno_bajo_stock:
                estado_receta = "BAJO_STOCK"
                estado_receta_label = "Bajo monto"
                alerta_receta = (
                    f"Alcanza para {ninos_presentes} estudiantes, pero quedarán con bajo monto: "
                    f"{', '.join(bajo_monto_nombres[:5])}."
                )
            else:
                estado_receta = "DISPONIBLE"
                estado_receta_label = "Disponible"
                alerta_receta = None

            resultados.append({
                "id_plato": None,
                "nombre_plato": nombre_plato,
                "id_seccion": id_seccion,
                "seccion_nombre": seccion_nombre,
                "gastronomia": "Colombiana PAE",
                "componente": comp_resumen or "Preparación tradicional colombiana adaptada al inventario",
                "componentes_detalle": componentes_det,
                "ninos_presentes": ninos_presentes,
                "ingredientes": lista_ingredientes_resultado,
                "pasos": s.get("pasos", [
                    "Desinfectar superficies, utensilios e ingredientes en la cocina escolar.",
                    "Realizar la cocción completa al estilo casero colombiano asegurando temperatura de inocuidad.",
                    "Porcionar de manera homogénea según los gramajes PAE para los estudiantes.",
                ]),
                "origen": "SUGERENCIA_IA",
                "etiqueta": f"Receta Colombiana IA para {seccion_nombre} ({ninos_presentes} raciones)",
                "viable_con_inventario": todos_alcanzan,
                "estado_inventario": estado_receta,
                "estado_inventario_label": estado_receta_label,
                "tiene_stock_bajo": alguno_bajo_stock,
                "tiene_agotados": alguno_agotado,
                "tiene_insuficientes": alguno_insuficiente,
                "alerta_inventario": alerta_receta,
                "imagen_url": None,
                "imagen": None,
                "imagen_cloudinary_public_id": None,
                "imagen_origen": None,
                "guardada_en_cloudinary": False,
            })
        return resultados

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
            sugerencias_estructuradas = _estructurar_y_validar(sugerencias_openai, solo_viables=True)
            uso_openai = bool(sugerencias_estructuradas)

        if not sugerencias_estructuradas:
            sugerencias_adaptadas = construir_sugerencias_adaptadas_al_inventario(
                seccion_nombre=seccion_nombre,
                ingredientes_suficientes=ingredientes_suficientes,
                ninos_presentes=ninos_presentes,
                mapa_inventario=mapa_inventario,
            )
            sugerencias_estructuradas = _estructurar_y_validar(sugerencias_adaptadas, solo_viables=True)

    inventario_suficiente = bool(sugerencias_estructuradas)

    # Si NO hay inventario suficiente para los N estudiantes (bajo monto / agotado / muchos estudiantes),
    # NO se debe generar ni devolver ninguna receta: se retornan las listas vacías y el mensaje claro.
    if not inventario_suficiente:
        sugerencias_estructuradas = []

    # 3. Generar imagen de la receta colombiana y guardarla en Cloudinary (solo si hay recetas viables)
    if generar_imagen and sugerencias_estructuradas:
        def _adjuntar_imagen(sug: dict) -> dict:
            img_info = generar_y_subir_imagen_receta(
                nombre_plato=sug["nombre_plato"],
                seccion_nombre=seccion_nombre,
                componentes_detalle=sug.get("componentes_detalle"),
                ingredientes=sug.get("ingredientes"),
            )
            sug["imagen_url"] = img_info.get("imagen_url")
            sug["imagen"] = img_info.get("imagen_url")
            sug["imagen_cloudinary_public_id"] = img_info.get("imagen_cloudinary_public_id")
            sug["imagen_origen"] = img_info.get("imagen_origen")
            sug["guardada_en_cloudinary"] = bool(img_info.get("guardada_en_cloudinary"))
            sug["imagen_prompt"] = img_info.get("imagen_prompt")
            return sug

        if len(sugerencias_estructuradas) == 1:
            _adjuntar_imagen(sugerencias_estructuradas[0])
        else:
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(_adjuntar_imagen, sugerencias_estructuradas))

    # 4. Evaluar platos base PAE estipulados contra el inventario real (solo si hay inventario suficiente)
    mapa_suf_nombres = {normalizar_texto(it["nombre"]): it for it in ingredientes_suficientes}
    platos_base_pae = []
    if inventario_suficiente:
        for b in CATALOGO_20_MENUS_PAE:
            if b["seccion"].lower() == seccion_nombre.lower():
                faltantes_base = [
                    ing_b
                    for ing_b in b["ingredientes"]
                    if buscar_en_mapa_inventario(ing_b, mapa_suf_nombres) is None
                ]
                base_viable = bool(b["ingredientes"]) and not faltantes_base
                platos_base_pae.append({
                    "id_plato": None,
                    "nombre_plato": b["nombre_plato"],
                    "id_seccion": id_seccion,
                    "seccion_nombre": b["seccion"],
                    "componente": f"{b['componentes']['bebida_leche']}, {b['componentes']['proteico']}, {b['componentes']['cereal']}",
                    "componentes_detalle": b["componentes"],
                    "ingredientes": b["ingredientes"],
                    "ingredientes_faltantes": faltantes_base,
                    "pasos": b["pasos"],
                    "origen": "PAE_ESTIPULADO",
                    "etiqueta": f"Menú Oficial PAE #{b['numeroMenu']}",
                    "viable_con_inventario": base_viable,
                    "estado_inventario": "DISPONIBLE" if base_viable else ("AGOTADO" if not mapa_inventario else "INSUFICIENTE"),
                })

    if inventario_suficiente:
        todas_las_opciones = sugerencias_estructuradas + [
            p for p in platos_base_pae if p["viable_con_inventario"]
        ]
    else:
        todas_las_opciones = []

    tiene_stock_real_positivo = any(
        Decimal(str(it.get("cantidad_actual") or 0)) > Decimal("0.00")
        for it in mapa_inventario.values()
    )

    if inventario_suficiente:
        if any(s.get("tiene_stock_bajo") for s in sugerencias_estructuradas) or ingredientes_bajo_stock:
            estado_inventario_general = "BAJO_STOCK"
            texto_resumen = (
                f"Se generaron {len(sugerencias_estructuradas)} propuestas de gastronomía colombiana para "
                f"{seccion_nombre} ({ninos_presentes} estudiantes), pero algunos ingredientes quedarán con "
                "bajo monto (por debajo del stock mínimo) tras la preparación."
            )
        else:
            estado_inventario_general = "DISPONIBLE"
            texto_resumen = (
                f"Se generaron {len(sugerencias_estructuradas)} propuestas de gastronomía colombiana adaptadas al "
                f"inventario real disponible para {seccion_nombre} ({ninos_presentes} estudiantes), sin repetir "
                "los menús oficiales del PAE."
            )
    elif not mapa_inventario or not tiene_stock_real_positivo:
        estado_inventario_general = "AGOTADO"
        texto_resumen = (
            f"No hay alimentos en el inventario para hacer una receta de {seccion_nombre} "
            f"para {ninos_presentes} estudiantes. Registra existencias en bodega para poder generar recetas."
        )
    elif ninos_maximos_atendibles > 0 and ninos_maximos_atendibles < ninos_presentes:
        estado_inventario_general = "INSUFICIENTE"
        texto_resumen = (
            f"No hay suficientes alimentos para hacer una receta de {seccion_nombre} "
            f"para {ninos_presentes} estudiantes (con el inventario actual solo alcanza para un máximo "
            f"aproximado de {ninos_maximos_atendibles} estudiantes). Abastece los ingredientes faltantes o ajusta la cantidad de raciones."
        )
    else:
        estado_inventario_general = "INSUFICIENTE"
        texto_resumen = (
            f"No hay suficientes alimentos para hacer una receta de {seccion_nombre} "
            f"para {ninos_presentes} estudiantes. Revisa los productos agotados o con stock insuficiente en el inventario."
        )

    resumen_inventario = {
        "estado_general": estado_inventario_general,
        "total_productos_sede": len(mapa_inventario),
        "total_disponibles": sum(1 for it in ingredientes_suficientes if it.get("estado_stock") == "DISPONIBLE"),
        "total_bajo_stock": len(ingredientes_bajo_stock),
        "total_insuficientes": sum(1 for it in ingredientes_insuficientes if not it.get("agotado")),
        "total_agotados": len(ingredientes_agotados),
    }

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
                "Google Gemini / OpenAI"
                if uso_openai
                else ("Motor PAE Colombiano" if inventario_suficiente else "Sin stock suficiente")
            ),
            "inventario_suficiente": inventario_suficiente,
            "estado_inventario_general": estado_inventario_general,
            "ninos_maximos_atendibles": ninos_maximos_atendibles,
            "total_sugerencias": len(sugerencias_estructuradas),
            "sugerencias": sugerencias_estructuradas,
            "ingredientes_bajo_stock": ingredientes_bajo_stock,
            "ingredientes_insuficientes": ingredientes_insuficientes,
            "ingredientes_agotados": ingredientes_agotados,
            "platos_base_pae_consultados": len(platos_base_pae),
        })
    except Exception as e:
        logger.warning("No se pudo registrar la sugerencia en MongoDB Atlas: %s", e)

    return Response(
        {
            "status": "success",
            "mensaje": texto_resumen,
            "seccion": seccion_nombre,
            "id_seccion": id_seccion,
            "ninos_presentes": ninos_presentes,
            "id_sede": id_sede_final,
            "inventario_suficiente": inventario_suficiente,
            "estado_inventario_general": estado_inventario_general,
            "resumen_inventario": resumen_inventario,
            "ninos_maximos_atendibles": ninos_maximos_atendibles,
            "sugerencias": texto_resumen,
            "sugerencias_ia_estructuradas": sugerencias_estructuradas,
            "ingredientes_disponibles_suficientes": [
                {
                    "id_ingrediente": it["id_ingrediente"],
                    "nombre_ingrediente": it["nombre"],
                    "stock_actual": str(it["cantidad_actual"]),
                    "stock_minimo": str(it.get("stock_minimo", Decimal("0.00"))),
                    "stock_restante_proyectado": str(it.get("stock_restante_proyectado", Decimal("0.00"))),
                    "unidad": it["unidad"],
                    "ninos_que_cubre": it["ninos_que_cubre"],
                    "stock_bajo": bool(it.get("stock_bajo")),
                    "estado_stock": it.get("estado_stock", "DISPONIBLE"),
                    "estado_stock_label": it.get("estado_stock_label", "Disponible"),
                }
                for it in ingredientes_suficientes
            ],
            "ingredientes_bajo_stock": ingredientes_bajo_stock,
            "ingredientes_insuficientes": ingredientes_insuficientes,
            "ingredientes_agotados": ingredientes_agotados,
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
# ENDPOINT: GENERAR IMAGEN DE RECETA COLOMBIANA Y GUARDARLA EN CLOUDINARY
# ==============================================================================
@api_view(["POST"])
@authentication_classes([OptionalJWTAuthentication])
@permission_classes([AllowAny])
def generar_imagen_receta_ia(request):
    """
    POST /api/ia/generar-imagen-receta/
    Genera una imagen representativa de una receta colombiana sugerida por la IA y la guarda
    en Cloudinary dentro de la carpeta `sirae_ia_recetas`.
    """
    data = request.data
    nombre_plato = str(data.get("nombre_plato") or "").strip()
    if not nombre_plato:
        return Response(
            {"error": "Debes enviar 'nombre_plato' para generar la imagen de la receta."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    raw_seccion = data.get("seccion") or data.get("id_seccion") or "Almuerzo"
    if isinstance(raw_seccion, int) or str(raw_seccion).isdigit():
        seccion_nombre = obtener_nombre_seccion(int(raw_seccion))
    else:
        seccion_nombre = str(raw_seccion).strip().capitalize()

    componentes_detalle = data.get("componentes_detalle")
    ingredientes = data.get("ingredientes") or data.get("ingredientes_usados")
    forzar = str(data.get("forzar_regeneracion", False)).strip().lower() in {"1", "true", "si", "yes"}

    resultado = generar_y_subir_imagen_receta(
        nombre_plato=nombre_plato,
        seccion_nombre=seccion_nombre,
        componentes_detalle=componentes_detalle,
        ingredientes=ingredientes,
        forzar_regeneracion=forzar,
    )

    if not resultado.get("guardada_en_cloudinary"):
        return Response(
            {
                "status": "success" if resultado.get("imagen_url") else "warning",
                "mensaje": (
                    "Imagen generada correctamente, pero Cloudinary no está configurado en el servidor. "
                    "Verifica CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY y CLOUDINARY_API_SECRET (o CLOUDINARY_URL) en Render."
                ),
                "nombre_plato": nombre_plato,
                "seccion": seccion_nombre,
                "imagen": resultado.get("imagen_url"),
                **resultado,
            },
            status=status.HTTP_200_OK if resultado.get("imagen_url") else status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        {
            "status": "success",
            "mensaje": "Imagen de la receta colombiana generada y guardada exitosamente en Cloudinary.",
            "nombre_plato": nombre_plato,
            "seccion": seccion_nombre,
            "imagen": resultado.get("imagen_url"),
            **resultado,
        },
        status=status.HTTP_200_OK,
    )


# ==============================================================================
# ENDPOINT: DESCONTAR INVENTARIO TRAS CONFIRMAR LA PREPARACIÓN
# ==============================================================================
@api_view(["POST"])
@authentication_classes([OptionalJWTAuthentication])
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
@authentication_classes([OptionalJWTAuthentication])
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
@authentication_classes([OptionalJWTAuthentication])
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

