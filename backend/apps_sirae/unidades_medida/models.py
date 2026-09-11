from django.db import models


class UnidadMedida(models.Model):
    id_unidad_medida = models.AutoField(primary_key=True)

    nombre = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    abreviatura = models.CharField(
        max_length=10,
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'unidades_medida'
        verbose_name = 'Unidad de Medida'
        verbose_name_plural = 'Unidades de Medida'

    def __str__(self):
        return f"{self.nombre} ({self.abreviatura})"