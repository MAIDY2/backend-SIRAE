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
            sede_obj = id_sede if hasattr(id_sede, 'id_sede') else None
            sede_id = sede_obj.id_sede if sede_obj else id_sede

            id_inst = getattr(instance, 'id_institucion', None)
            if not id_inst and sede_obj and getattr(sede_obj, 'id_institucion', None):
                id_inst = sede_obj.id_institucion

            cant = Decimal(str(instance.cantidad or 0))

            filtro = {'id_ingrediente': id_ing}
            if sede_id is not None:
                filtro['id_sede_id'] = sede_id
            else:
                filtro['id_sede__isnull'] = True

            # Buscar si ya existe registro para este ingrediente y sede
            registros = list(Inventario.objects.filter(**filtro).order_by('id_inventario'))

            if registros:
                inventario = registros[0]
                inventario.cantidad_actual = (inventario.cantidad_actual or Decimal('0.00')) + cant
                if id_inst and not inventario.id_institucion_id:
                    inventario.id_institucion = id_inst
                inventario.save()

                # Consolidar duplicados previos si existían
                if len(registros) > 1:
                    for dup in registros[1:]:
                        inventario.cantidad_actual += (dup.cantidad_actual or Decimal('0.00'))
                        dup.delete()
                    inventario.save()
            else:
                inventario = Inventario.objects.create(
                    id_ingrediente=id_ing,
                    id_sede_id=sede_id,
                    id_institucion=id_inst,
                    cantidad_actual=cant,
                    stock_minimo=Decimal('0.00'),
                    id_unidad_medida=(
                        getattr(instance, 'id_unidad_medida_id', None)
                        or getattr(instance, 'id_unidad_medida', 1)
                        or 1
                    )
                )

            # Si es una ENTREGA realizada por el supervisor, descontar del Inventario Central y del Inventario Global
            if sender == Entrega:
                inv_central = InventarioCentral.objects.filter(id_ingrediente_id=id_ing).first()
                if inv_central:
                    inv_central.cantidad_disponible = max(
                        Decimal('0.000'),
                        Decimal(str(inv_central.cantidad_disponible)) - cant
                    )
                    inv_central.save(update_fields=['cantidad_disponible', 'fecha_ultima_actualizacion'])

                if sede_id is not None:
                    inv_global = Inventario.objects.filter(id_ingrediente=id_ing, id_sede__isnull=True).first()
                    if inv_global:
                        inv_global.cantidad_actual = max(
                            Decimal('0.00'),
                            Decimal(str(inv_global.cantidad_actual or 0)) - cant
                        )
                        inv_global.save(update_fields=['cantidad_actual'])


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
            id_sede = getattr(instance, 'id_sede', None)
            sede_id = id_sede.id_sede if hasattr(id_sede, 'id_sede') else id_sede

            filtro = {'id_ingrediente': id_ing}
            if sede_id is not None:
                filtro['id_sede_id'] = sede_id

            inventario = Inventario.objects.filter(**filtro).first()
            if not inventario and sede_id is not None:
                inventario = Inventario.objects.filter(id_ingrediente=id_ing).first()

            if inventario:
                inventario.cantidad_actual = max(
                    Decimal('0.00'),
                    (inventario.cantidad_actual or Decimal('0.00')) - Decimal(str(instance.cantidad or 0))
                )
                inventario.save()
