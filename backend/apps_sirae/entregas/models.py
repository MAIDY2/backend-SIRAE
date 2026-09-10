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

    class Meta:
        db_table = 'entregas'