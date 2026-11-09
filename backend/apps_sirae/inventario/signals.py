from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

from apps_sirae.entregas.models import Entrega
from apps_sirae.inventario.models import Inventario
from apps_sirae.facturas_compra.models import InventarioCentral


@receiver(post_save, sender=Entrega)
def descontar_inventario_al_despachar(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            id_ing = instance.id_ingrediente
            sede_id = instance.id_sede_id
            cant = Decimal(str(instance.cantidad or 0))

            inv_central = InventarioCentral.objects.select_for_update().filter(
                id_ingrediente_id=id_ing
            ).first()
            if inv_central:
                inv_central.cantidad_disponible = max(
                    Decimal('0.000'),
                    Decimal(str(inv_central.cantidad_disponible)) - cant
                )
                inv_central.save(update_fields=['cantidad_disponible', 'fecha_ultima_actualizacion'])

            if sede_id is not None:
                inv_global = Inventario.objects.select_for_update().filter(
                    id_ingrediente=id_ing,
                    id_sede__isnull=True,
                    id_institucion__isnull=True,
                ).first()
                if inv_global:
                    inv_global.cantidad_actual = max(
                        Decimal('0.00'),
                        Decimal(str(inv_global.cantidad_actual or 0)) - cant
                    )
                    inv_global.save(update_fields=['cantidad_actual'])
