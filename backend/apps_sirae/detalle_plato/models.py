from django.db import models
from apps_sirae.platos.models import Plato
from apps_sirae.unidades_medida.models import UnidadMedida


class DetallePlato(models.Model):
    id_detalle_plato = models.AutoField(primary_key=True)
    id_plato = models.ForeignKey(
        Plato,
        on_delete=models.CASCADE,
        related_name='detalles',
        db_column='id_plato',
        verbose_name="Plato"
    )
    ingrediente = models.CharField(max_length=150, verbose_name="Nombre del Ingrediente / Insumo")
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad")
    id_unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.RESTRICT,
        related_name='detalles_plato',
        db_column='id_unidad_medida',
        verbose_name="Unidad de Medida"
    )
    observaciones = models.TextField(null=True, blank=True, verbose_name="Observaciones / Instrucciones")

    class Meta:
        db_table = 'detalle_plato'
        verbose_name = 'Detalle de Plato'
        verbose_name_plural = 'Detalles de Plato'

    def __str__(self):
        return f"{self.ingrediente} - {self.cantidad} ({self.id_plato.nombre})"