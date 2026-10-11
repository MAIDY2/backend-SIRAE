from django.db import models
from apps_sirae.instituciones.models import Institucion


class Sede(models.Model):
  id_sede = models.AutoField(primary_key=True)
  id_institucion = models.ForeignKey(
      Institucion,
      on_delete=models.CASCADE,
      db_column='id_institucion',
      related_name='sedes',
  )
  nombre_sede = models.CharField(max_length=150)
  codigo_dane = models.CharField(max_length=50, blank=True, null=True)
  direccion = models.CharField(max_length=200, blank=True, null=True)
  telefono = models.CharField(max_length=30, blank=True, null=True)
  estado = models.CharField(max_length=20, default='ACTIVO')

  class Meta:
    db_table = 'sedes'
    