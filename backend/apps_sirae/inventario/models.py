from django.db import models

class Inventario(models.Model):
    objects = models.Manager()

    id_inventario = models.AutoField(primary_key=True)
    id_ingrediente = models.IntegerField()
    cantidad_actual = models.DecimalField(max_digits=10, decimal_places=2)
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2)
    id_unidad_medida = models.IntegerField()
    id_institucion = models.ForeignKey(
        'instituciones.Institucion',
        on_delete=models.CASCADE,
        db_column='id_institucion',
        null=True,
        blank=True,
        related_name='inventarios'
    )
    id_sede = models.ForeignKey(
        'sedes.Sede',
        on_delete=models.CASCADE,
        db_column='id_sede',
        null=True,
        blank=True,
        related_name='inventarios'
    )

    class Meta:
        db_table = 'inventario'

    def __str__(self):
        return f"Inventario {self.id_inventario} - Ingrediente {self.id_ingrediente}"