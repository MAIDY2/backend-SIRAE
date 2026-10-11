from django.db import models


class Institucion(models.Model):
  id_institucion = models.AutoField(primary_key=True)
  nombre_institucion = models.CharField(max_length=150)
  nit = models.CharField(max_length=50, unique=True)
  representante_legal = models.CharField(max_length=150, blank=True, null=True)
  telefono = models.CharField(max_length=30, blank=True, null=True)
  correo_contacto = models.CharField(max_length=150, blank=True, null=True)
  estado = models.CharField(max_length=20, default='ACTIVO')

  class Meta:
    db_table = 'instituciones'
    