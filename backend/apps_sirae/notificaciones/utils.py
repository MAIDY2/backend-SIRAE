"""
Utilidades para el módulo de notificaciones y despacho de correos en SIRAE PAE.
"""

from .services import (
    construir_plantilla_notificacion_html,
    enviar_correo,
    enviar_correo_notificacion,
    enviar_alerta_stock_inventario,
    notificar_usuarios_por_correo,
)

__all__ = [
    "construir_plantilla_notificacion_html",
    "enviar_correo",
    "enviar_correo_notificacion",
    "enviar_alerta_stock_inventario",
    "notificar_usuarios_por_correo",
]
