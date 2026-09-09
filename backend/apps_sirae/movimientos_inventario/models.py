from django.db import models


class MovimientoInventario(models.Model):
    id_movimiento_inventario = models.AutoField(primary_key=True)
    id_ingrediente = models.IntegerField()
    id_usuario_manipuladora = models.IntegerField()
    tipo_movimiento = models.CharField(max_length=30)
    fecha = models.DateTimeField()
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    observaciones = models.TextField(blank=True)
    id_unidad_medida = models.IntegerField()

    class Meta:
        db_table = 'movimientos_inventario'