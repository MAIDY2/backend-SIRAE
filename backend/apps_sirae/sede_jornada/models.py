from apps_sirae.jornadas.models import Jornada  
from django.db import models


class SedeJornada(models.Model):
  id_sede_jornada = models.AutoField(primary_key=True)
  id_sede = models.ForeignKey(
      'sedes.Sede',
      on_delete=models.CASCADE,
      db_column='id_sede',
      related_name='sede_jornadas',
  )
  id_jornada = models.ForeignKey(
      Jornada,
      on_delete=models.CASCADE,
      db_column='id_jornada',
      related_name='sede_jornadas',
  )

  class Meta:
    db_table = 'sede_jornada'
    unique_together = ('id_sede', 'id_jornada')