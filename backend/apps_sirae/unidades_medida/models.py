from django.db import models


class UnidadMedida(models.Model):
    id_unidad_medida = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    abreviatura = models.CharField(max_length=20)

    class Meta:
        db_table = 'unidades_medida'

    def __str__(self):
        return f"{self.nombre} ({self.abreviatura})"