from django.db import models


class UnidadMedida(models.Model):
    id_unidad_medida = models.AutoField(primary_key=True)
    nombre_unidad = models.CharField(max_length=50)
    abreviatura = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        db_table = 'unidades_medida'

    def __str__(self):
        return self.nombre_unidad or ''