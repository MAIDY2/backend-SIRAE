from django.db import models


class UnidadMedida(models.Model):
    id_unidad_medida = models.AutoField(primary_key=True)
    nombre_unidad = models.CharField(max_length=50)
    abreviatura = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        db_table = 'unidades_medida'
        managed = True  # <--- AQUÍ SE AGREGA
        verbose_name = 'Unidad de medida'
        verbose_name_plural = 'Unidades de medida'

    def __str__(self):
        return self.nombre_unidad or ''