from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

# Importaciones de los modelos con sus nombres exactos
from apps_sirae.inventario.models import Inventario
from apps_sirae.entradas_inventario.models import EntradaInventario
from apps_sirae.salidas_inventario.models import SalidaInventario
from apps_sirae.entregas.models import Entrega  
from apps_sirae.facturas_compra.models import InventarioCentral


# 1. Al registrar una ENTRADA o ENTREGA -> SUMAR AL INVENTARIO DE LA SEDE
@receiver(post_save, sender=EntradaInventario)
@receiver(post_save, sender=Entrega)
def sumar_al_inventario(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            # Soporta si id_ingrediente es un IntegerField o una ForeignKey
            id_ing = (
                instance.id_ingrediente.id_ingrediente
                if hasattr(instance.id_ingrediente, 'id_ingrediente')
                else instance.id_ingrediente
            )
            id_sede = getattr(instance, 'id_sede', None)

            inventario, _ = Inventario.objects.get_or_create(
                id_ingrediente=id_ing,
                id_sede=id_sede,
                defaults={
                    'cantidad_actual': Decimal('0.00'),
                    'stock_minimo': Decimal('0.00'),
                    'id_unidad_medida': getattr(instance, 'id_unidad_medida', 1)
                }
            )
            inventario.cantidad_actual += Decimal(str(instance.cantidad or 0))
            inventario.save()

            # Si es una ENTREGA realizada por el supervisor, descontar del Inventario Central
            if sender == Entrega:
                inv_central = InventarioCentral.objects.filter(id_ingrediente_id=id_ing).first()
                if inv_central:
                    inv_central.cantidad_disponible = max(
                        Decimal('0.000'),
                        Decimal(str(inv_central.cantidad_disponible)) - Decimal(str(instance.cantidad or 0))
                    )
                    inv_central.save(update_fields=['cantidad_disponible', 'fecha_ultima_actualizacion'])


# 2. Al registrar una SALIDA -> RESTAR DEL INVENTARIO
@receiver(post_save, sender=SalidaInventario)
def restar_del_inventario(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            id_ing = (
                instance.id_ingrediente.id_ingrediente
                if hasattr(instance.id_ingrediente, 'id_ingrediente')
                else instance.id_ingrediente
            )

            inventario = Inventario.objects.filter(id_ingrediente=id_ing).first()
            if inventario:
                inventario.cantidad_actual -= Decimal(str(instance.cantidad or 0))
                inventario.save()