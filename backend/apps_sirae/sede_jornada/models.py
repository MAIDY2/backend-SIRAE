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
  cupos = models.IntegerField(default=0)

  class Meta:
    db_table = 'sede_jornada'
    unique_together = ('id_sede', 'id_jornada')

  def __str__(self):
    sede = getattr(self.id_sede, 'nombre_sede', f'Sede {self.id_sede_id}')
    jornada = getattr(self.id_jornada, 'nombre_jornada', f'Jornada {self.id_jornada_id}')
    return f"{sede} - {jornada}"


class SedeJornadaGrado(models.Model):
    """
    Grados escolares atendidos en una sede y jornada específica.
    """
    ESTADOS = [
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo'),
    ]

    id_sede_jornada_grado = models.AutoField(primary_key=True)
    id_sede_jornada = models.ForeignKey(
        SedeJornada,
        on_delete=models.CASCADE,
        db_column='id_sede_jornada',
        related_name='grados_atendidos',
    )
    id_grado = models.ForeignKey(
        'grados.Grados',
        on_delete=models.PROTECT,
        db_column='id_grado',
        related_name='sede_jornadas_atencion',
    )
    cupos = models.PositiveIntegerField(default=0)
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='ACTIVO',
    )

    class Meta:
        db_table = 'sede_jornada_grados'
        unique_together = ('id_sede_jornada', 'id_grado')
        ordering = ['id_grado__id_grado']

    def __str__(self):
        return f"{self.id_sede_jornada} - {self.id_grado}"
