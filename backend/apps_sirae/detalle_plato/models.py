from django.db import models
class DetallePlato(models.Model):
    id_detalle_plato = models.AutoField(primary_key=True)
    id_menu = models.IntegerField(null=True, blank=True)
    id_plato = models.IntegerField(null=True, blank=True)
    porcion_por_nino = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_a_preparar = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unidad_total = models.CharField(max_length=20, null=True, blank=True)
    estado_preparacion = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'detalle_plato'
        managed = False

    def __str__(self):
        return f"Detalle {self.id_detalle_plato}"