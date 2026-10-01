from django.db import models
from django.conf import settings

from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.unidades_medida.models import UnidadMedida


class SalidaInventario(models.Model):

    id_salida = models.AutoField(primary_key=True)

    id_ingrediente = models.ForeignKey(
        Ingrediente,
        on_delete=models.PROTECT,
        db_column='id_ingrediente'
    )

    id_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_usuario'
    )

    fecha = models.DateTimeField(
        null=True,
        blank=True
    )

    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    id_unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.PROTECT,
        db_column='id_unidad_medida'
    )

    observaciones = models.TextField(
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'salidas_inventario'
        managed = False

    def __str__(self):
        return f"Salida - {self.id_ingrediente} ({self.cantidad})"