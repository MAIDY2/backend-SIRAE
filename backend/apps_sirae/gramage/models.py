from django.db import models

class Gramage(models.Model):
    id_gramage = models.AutoField(primary_key=True)
    id_ingrediente = models.IntegerField()
    id_grado = models.IntegerField()
    id_unidad_medida = models.IntegerField()
    cantidad_gramage = models.DecimalField(max_digits=10, decimal_places=2)
    descripcion = models.CharField(max_length=255)

    def __str__(self):
        return f"Gramage {self.id_gramage} - Ingrediente {self.id_ingrediente}"

    class Meta:
        db_table = 'gramage_gramage'
        managed = False