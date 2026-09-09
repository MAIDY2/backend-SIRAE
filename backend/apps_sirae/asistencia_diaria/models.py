from django.db import models


class AsistenciaDiaria(models.Model):
    id_asistencia = models.AutoField(primary_key=True)
    id_grado = models.IntegerField()
    fecha = models.DateField()
    ninos_presentes = models.PositiveIntegerField()
    id_usuario_manipuladora = models.IntegerField()

    class Meta:
        db_table = 'asistencia_diaria'