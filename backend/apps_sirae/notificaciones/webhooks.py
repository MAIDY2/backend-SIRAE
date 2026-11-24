import os
import json
import logging
import threading
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

def _disparar_peticion_http(url: str, payload: dict):
    """Envía la petición HTTP POST de manera síncrona en un hilo secundario."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "SIRAE-Backend-Webhook/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            logger.info(f"[n8n-Webhook] Enviado con éxito a {url} - Status: {response.status}")
    except urllib.error.URLError as e:
        logger.warning(f"[n8n-Webhook] No se pudo conectar a {url}: {e}")
    except Exception as e:
        logger.error(f"[n8n-Webhook] Error inesperado enviando webhook: {e}")


def enviar_webhook_asincrono(url: str, payload: dict):
    """
    Envía el payload a la URL de n8n en segundo plano (Thread) para evitar
    demorar las respuestas HTTP principales de Django.
    """
    if not url:
        return
    hilo = threading.Thread(target=_disparar_peticion_http, args=(url, payload), daemon=True)
    hilo.start()


def notificar_ingrediente_n8n(ingrediente):
    """
    Notifica a n8n cuando un ingrediente necesita asignación automática de imagen
    y subida a Cloudinary.
    """
    url = os.getenv("N8N_WEBHOOK_INGREDIENTES_URL", "").strip()
    if not url:
        return

    payload = {
        "evento": "ingrediente_creado_sin_imagen",
        "id_ingrediente": ingrediente.id_ingrediente,
        "nombre_ingrediente": ingrediente.nombre_ingrediente or "",
        "descripcion": ingrediente.descripcion or "",
        "tipo_conservacion": getattr(ingrediente, "tipo_conservacion", "no_perecedero"),
    }
    enviar_webhook_asincrono(url, payload)


def notificar_despacho_n8n(entrega):
    """
    Notifica a n8n cuando se genera un despacho de alimentos (FAC-...) para alertar
    a la institución educativa y al supervisor.
    """
    url = os.getenv("N8N_WEBHOOK_DESPACHOS_URL", "").strip()
    if not url:
        return

    institucion_nombre = ""
    sede_nombre = ""
    if entrega.id_institucion:
        institucion_nombre = getattr(entrega.id_institucion, "nombre_institucion", "")
    if entrega.id_sede:
        sede_nombre = getattr(entrega.id_sede, "nombre_sede", "")

    payload = {
        "evento": "despacho_alimentos_en_transito",
        "id_entrega": entrega.id_entrega,
        "documento_entrega": entrega.documento_entrega or f"ENT-{entrega.id_entrega}",
        "fecha_entrega": str(entrega.fecha_entrega),
        "institucion_nombre": institucion_nombre,
        "sede_nombre": sede_nombre,
        "cantidad": str(entrega.cantidad),
        "unidad": entrega.unidad or "unidades",
        "estado": entrega.estado,
    }
    enviar_webhook_asincrono(url, payload)


def notificar_novedad_n8n(entrega):
    """
    Notifica a n8n cuando un administrador reporta una novedad técnica o rechaza
    una factura de alimentos PAE.
    """
    url = os.getenv("N8N_WEBHOOK_NOVEDADES_URL", "").strip()
    if not url:
        return

    institucion_nombre = ""
    if entrega.id_institucion:
        institucion_nombre = getattr(entrega.id_institucion, "nombre_institucion", "")

    payload = {
        "evento": "alerta_novedad_pae",
        "id_entrega": entrega.id_entrega,
        "documento_entrega": entrega.documento_entrega,
        "institucion_nombre": institucion_nombre,
        "estado": entrega.estado,
        "cantidad_rechazada": str(entrega.cantidad_rechazada),
        "motivo_rechazo": entrega.motivo_rechazo or "Sin motivo especificado",
        "fecha_recepcion": str(entrega.fecha_recepcion) if entrega.fecha_recepcion else "",
    }
    enviar_webhook_asincrono(url, payload)
