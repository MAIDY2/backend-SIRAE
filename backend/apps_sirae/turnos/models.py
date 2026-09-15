from django.db import models


class Turno(models.Model):
    id_turno = models.AutoField(primary_key=True)

    nombre_turno = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    hora_inicio = models.TimeField(
        null=True,
        blank=True
    )

    hora_fin = models.TimeField(
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'turnos'

    def __str__(self):
        return self.nombre_turno or ''