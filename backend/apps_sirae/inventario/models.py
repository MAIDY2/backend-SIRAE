from django.db import models

class Inventario(models.Model):
    id_inventario = models.AutoField(primary_key=True)
    id_ingrediente = models.IntegerField()
    cantidad_actual = models.DecimalField(max_digits=10, decimal_places=2)
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2)
    id_unidad_medida = models.IntegerField()

    class Meta:
        db_table = 'inventario'
        managed = False

    def __str__(self):
        return f"Inventario {self.id_inventario} - Ingrediente {self.id_ingrediente}"