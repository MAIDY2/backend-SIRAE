import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

_mongo_client = None
_mongo_db = None


def get_mongo_uri() -> str:
    """Obtiene la URI de conexión a MongoDB Atlas desde settings o variables de entorno."""
    return getattr(settings, "MONGO_URI", "") or os.getenv("MONGO_URI", os.getenv("MONGODB_URI", "")).strip()


def get_mongo_db_name() -> str:
    """Obtiene el nombre de la base de datos de MongoDB Atlas."""
    return getattr(settings, "MONGO_DB_NAME", "") or os.getenv("MONGO_DB_NAME", "sirae_ia").strip()


def get_mongo_client():
    """Retorna una instancia reutilizable del cliente de MongoDB Atlas."""
    global _mongo_client
    uri = get_mongo_uri()
    if not uri:
        return None

    if _mongo_client is None:
        try:
            from pymongo import MongoClient
            _mongo_client = MongoClient(
                uri,
                serverSelectionTimeoutMS=3000,
                connectTimeoutMS=3000,
                socketTimeoutMS=5000,
                retryWrites=True,
                appname="SIRAE-Backend-IA",
            )
        except Exception as e:
            logger.warning("No se pudo inicializar MongoClient para MongoDB Atlas: %s", e)
            return None

    return _mongo_client


def get_mongo_db():
    """Retorna la base de datos de MongoDB Atlas configurada para la IA."""
    global _mongo_db
    client = get_mongo_client()
    if client is None:
        return None

    db_name = get_mongo_db_name()
    try:
        _mongo_db = client[db_name]
        return _mongo_db
    except Exception as e:
        logger.warning("Error al obtener la base de datos '%s' en MongoDB Atlas: %s", db_name, e)
        return None


def verificar_conexion_mongo() -> Dict[str, Any]:
    """
    Verifica el estado de la conexión a MongoDB Atlas ejecutando un comando ping.
    Retorna un diccionario detallado para diagnóstico y monitoreo.
    """
    uri = get_mongo_uri()
    db_name = get_mongo_db_name()

    if not uri:
        return {
            "conectado": False,
            "motivo": "MONGO_URI no configurada en las variables de entorno (.env o Render)",
            "database": db_name,
            "colecciones": [],
        }

    try:
        client = get_mongo_client()
        if client is None:
            return {
                "conectado": False,
                "motivo": "No se pudo instanciar el cliente PyMongo",
                "database": db_name,
                "colecciones": [],
            }

        # Ejecutar ping en la base de datos de administración
        client.admin.command("ping")
        db = client[db_name]
        colecciones = db.list_collection_names()

        return {
            "conectado": True,
            "mensaje": "Conexión exitosa con el clúster de MongoDB Atlas",
            "database": db_name,
            "colecciones": colecciones,
        }
    except Exception as e:
        logger.warning("Fallo al conectar con MongoDB Atlas: %s", e)
        return {
            "conectado": False,
            "motivo": f"Error de conexión con MongoDB Atlas: {str(e)}",
            "database": db_name,
            "colecciones": [],
        }


def guardar_historial_sugerencia(registro: Dict[str, Any]) -> Optional[str]:
    """
    Guarda en MongoDB Atlas el registro estructurado de una sugerencia generada por la IA.
    Colección: `historial_sugerencias_ia`
    """
    db = get_mongo_db()
    if db is None:
        return None

    try:
        coleccion = db["historial_sugerencias_ia"]
        doc = dict(registro)
        if "fecha_creacion" not in doc:
            doc["fecha_creacion"] = datetime.utcnow()

        res = coleccion.insert_one(doc)
        return str(res.inserted_id)
    except Exception as e:
        logger.warning("Error al registrar sugerencia en MongoDB Atlas: %s", e)
        return None


def obtener_historial_sugerencias(
    limite: int = 20,
    id_sede: Optional[int] = None,
    seccion: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Consulta los registros de sugerencias generadas por la IA almacenados en MongoDB Atlas.
    """
    db = get_mongo_db()
    if db is None:
        return []

    try:
        coleccion = db["historial_sugerencias_ia"]
        filtro: Dict[str, Any] = {}
        if id_sede is not None:
            filtro["id_sede"] = id_sede
        if seccion:
            filtro["seccion"] = seccion

        cursor = coleccion.find(filtro).sort("fecha_creacion", -1).limit(limite)
        resultados = []
        for item in cursor:
            item["_id"] = str(item["_id"])
            if isinstance(item.get("fecha_creacion"), datetime):
                item["fecha_creacion"] = item["fecha_creacion"].isoformat()
            resultados.append(item)
        return resultados
    except Exception as e:
        logger.warning("Error al consultar historial de sugerencias en MongoDB Atlas: %s", e)
        return []


def guardar_auditoria_consumo(registro: Dict[str, Any]) -> Optional[str]:
    """
    Registra en MongoDB Atlas el descuento y consumo real tras la preparación del menú sugerido.
    Colección: `auditoria_consumos_ia`
    """
    db = get_mongo_db()
    if db is None:
        return None

    try:
        coleccion = db["auditoria_consumos_ia"]
        doc = dict(registro)
        if "fecha" not in doc:
            doc["fecha"] = datetime.utcnow()

        res = coleccion.insert_one(doc)
        return str(res.inserted_id)
    except Exception as e:
        logger.warning("Error al registrar auditoría de consumo en MongoDB Atlas: %s", e)
        return None


def sincronizar_catalogo_recetas(catalogo_20_menus: List[Dict[str, Any]]) -> int:
    """
    Sincroniza la base de conocimiento de recetas y menús del PAE en MongoDB Atlas.
    Colección: `catalogo_recetas_ia`
    """
    db = get_mongo_db()
    if db is None:
        return 0

    try:
        coleccion = db["catalogo_recetas_ia"]
        count = coleccion.count_documents({})
        if count == 0 and catalogo_20_menus:
            documentos = []
            for item in catalogo_20_menus:
                copia = dict(item)
                copia["sincronizado_en"] = datetime.utcnow()
                documentos.append(copia)
            res = coleccion.insert_many(documentos)
            return len(res.inserted_ids)
        return count
    except Exception as e:
        logger.warning("Error al sincronizar catálogo en MongoDB Atlas: %s", e)
        return 0


def obtener_recetas_catalogo_mongo(seccion: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Obtiene recetas base almacenadas en MongoDB Atlas.
    """
    db = get_mongo_db()
    if db is None:
        return []

    try:
        coleccion = db["catalogo_recetas_ia"]
        filtro = {}
        if seccion:
            filtro["seccion"] = {"$regex": f"^{seccion}$", "$options": "i"}

        cursor = coleccion.find(filtro).sort("numeroMenu", 1)
        recetas = []
        for r in cursor:
            r["_id"] = str(r["_id"])
            if isinstance(r.get("sincronizado_en"), datetime):
                r["sincronizado_en"] = r["sincronizado_en"].isoformat()
            recetas.append(r)
        return recetas
    except Exception as e:
        logger.warning("Error al obtener recetas de MongoDB Atlas: %s", e)
        return []
