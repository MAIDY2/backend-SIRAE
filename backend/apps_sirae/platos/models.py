from django.db import models


class Plato(models.Model):
    id_plato = models.AutoField(primary_key=True)

    id_seccion = models.ForeignKey(
        'secciones_menu.SeccionMenu',
        on_delete=models.DO_NOTHING,
        db_column='id_seccion',
        null=True,
        blank=True
    )

    nombre_plato = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    componente = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'platos'
        managed = False

    def __str__(self):
        return self.nombre_plato or ''