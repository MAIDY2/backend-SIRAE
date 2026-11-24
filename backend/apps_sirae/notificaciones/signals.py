import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.entregas.models import Entrega
from .webhooks import (
    notificar_ingrediente_n8n,
    notificar_despacho_n8n,
    notificar_novedad_n8n,
)

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Ingrediente)
def hook_ingrediente_creado(sender, instance, created, **kwargs):
    """
    Si se crea un ingrediente nuevo o no tiene imagen alojada en Cloudinary,
    dispara el webhook a n8n para que busque y suba la foto automáticamente.
    """
    imagen_actual = instance.imagen_ingrediente or ""
    if not imagen_actual or "res.cloudinary.com" not in imagen_actual:
        notificar_ingrediente_n8n(instance)


@receiver(post_save, sender=Entrega)
def hook_entrega_actualizada(sender, instance, created, **kwargs):
    """
    Si se crea una entrega en estado EN_TRANSITO, notifica a n8n para avisar a la sede.
    Si se actualiza a CON_NOVEDAD o RECHAZADA, notifica la alerta técnica.
    """
    if created and instance.estado == "EN_TRANSITO":
        notificar_despacho_n8n(instance)
    elif not created and instance.estado in ("CON_NOVEDAD", "RECHAZADA"):
        notificar_novedad_n8n(instance)
