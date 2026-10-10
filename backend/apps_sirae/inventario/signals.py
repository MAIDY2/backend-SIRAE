from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

# Importaciones de los modelos con sus nombres exactos
from apps_sirae.inventario.models import Inventario
from apps_sirae.entradas_inventario.models import EntradaInventario
from apps_sirae.salidas_inventario.models import SalidaInventario
from apps_sirae.entregas.models import Entrega  


# 1. Al registrar una ENTRADA o ENTREGA -> SUMAR AL INVENTARIO
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

            inventario, _ = Inventario.objects.get_or_create(
                id_ingrediente=id_ing,
                defaults={
                    'cantidad_actual': 0,
                    'stock_minimo': 0,
                    'id_unidad_medida': getattr(instance, 'id_unidad_medida', 1)
                }
            )
            inventario.cantidad_actual += instance.cantidad
            inventario.save()


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

            inventario = Inventario.objects.get(id_ingrediente=id_ing)
            inventario.cantidad_actual -= instance.cantidad
            inventario.save()