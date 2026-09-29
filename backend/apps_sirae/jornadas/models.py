from django.db import models


class Jornada(models.Model):
    id_jornada = models.AutoField(primary_key=True)
    nombre_jornada = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'jornadas'
        managed = False

    def __str__(self):
        return f"Jornada {self.id_jornada}: {self.nombre_jornada}"