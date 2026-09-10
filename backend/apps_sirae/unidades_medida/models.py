from django.db import models


class UnidadMedida(models.Model):
    id_unidad_medida = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True, verbose_name="Nombre de la unidad")
    abreviatura = models.CharField(max_length=10, unique=True, verbose_name="Abreviatura")
    descripcion = models.CharField(max_length=150, null=True, blank=True, verbose_name="Descripción")

    class Meta:
        db_table = 'unidades_medida'
        verbose_name = 'Unidad de Medida'
        verbose_name_plural = 'Unidades de Medida'

    def __str__(self):
        return f"{self.nombre} ({self.abreviatura})"