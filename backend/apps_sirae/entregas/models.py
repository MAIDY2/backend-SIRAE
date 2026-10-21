from django.db import models


class Entrega(models.Model):
    id_entrega = models.AutoField(primary_key=True)
    id_ingrediente = models.IntegerField()
    id_usuario_supervisor = models.IntegerField()
    id_tipo_mercado = models.IntegerField()
    fecha_entrega = models.DateField()
    fecha_vencimiento = models.DateField()
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    observaciones = models.TextField(blank=True)
    frecuencia = models.CharField(max_length=20, blank=True, default='')
    unidad = models.CharField(max_length=30, blank=True, default='')
    id_sede = models.ForeignKey(
        'sedes.Sede',
        on_delete=models.RESTRICT,
        db_column='id_sede',
        null=True,
        blank=True,
        related_name='entregas'
    )

    class Meta:
        db_table = 'entregas'