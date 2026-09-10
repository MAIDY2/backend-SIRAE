# -*- coding: utf-8 -*-
from django.db import models


class Rol(models.Model):

    class NombreRol(models.TextChoices):
        ADMINISTRADOR      = 'Administrador',     'Administrador'
        SUPERVISOR         = 'Supervisor',        'Supervisor'
        JEFA_MANIPULADORAS = 'JefaManipuladoras', 'Jefa de Manipuladoras'
        MANIPULADORA       = 'Manipuladora',      'Manipuladora de alimentos'

    id_rol      = models.AutoField(primary_key=True)
    nombre      = models.CharField(
                    max_length=30,
                    choices=NombreRol.choices,
                    unique=True
                  )
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table            = 'roles'
        verbose_name        = 'Rol'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.get_nombre_display()
