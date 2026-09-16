from django.db import models

from apps_sirae.platos.models import Plato
from apps_sirae.ingredientes.models import Ingrediente


class RecetaComponente(models.Model):
    id_receta_componente = models.AutoField(
        primary_key=True
    )

    id_plato = models.ForeignKey(
        Plato,
        on_delete=models.CASCADE,
        db_column='id_plato',
        related_name='receta_componentes'
    )

    id_ingrediente = models.ForeignKey(
        Ingrediente,
        on_delete=models.CASCADE,
        db_column='id_ingrediente',
        related_name='receta_componentes'
    )

    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    class Meta:
        db_table = 'receta_componente'
        managed = True
        verbose_name = 'Receta componente'
        verbose_name_plural = 'Recetas componentes'

    def __str__(self):
        return f"Receta componente {self.id_receta_componente}"
