from django.db import models
from apps_sirae.grados.models import Grados


class Gramage(models.Model):
    id_gramaje = models.AutoField(
        primary_key=True,
        db_column='id_gramaje'
    )

    id_ingrediente = models.ForeignKey(
        'ingredientes.Ingrediente',
        on_delete=models.DO_NOTHING,
        db_column='id_ingrediente',
        null=True,
        blank=True,
        related_name='gramajes'
    )

    id_grado = models.ForeignKey(
        Grados,
        on_delete=models.CASCADE,
        db_column='id_grado',
        null=True,
        blank=True,
        related_name='gramajes'
    )

    id_unidad_medida = models.ForeignKey(
        'unidades_medida.UnidadMedida',
        on_delete=models.DO_NOTHING,
        db_column='id_unidad_medida',
        null=True,
        blank=True,
        related_name='gramajes'
    )

    cantidad_gramaje = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        db_column='cantidad_gramaje'
    )

    descripcion = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'gramajes'
        managed = True

    def __str__(self):
        grado_nom = self.id_grado.nombre_grado if self.id_grado else "Sin grado"
        return f"Gramaje {self.id_gramaje} - Grado: {grado_nom}"

    # Alias de compatibilidad hacia atrás (con 'g')
    @property
    def id_gramage(self):
        return self.id_gramaje

    @property
    def cantidad_gramage(self):
        return self.cantidad_gramaje